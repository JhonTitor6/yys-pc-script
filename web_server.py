import asyncio
import inspect
import json
import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Type

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # 添加Request导入
from loguru import logger

from yys.event_script_base import YYSBaseScript

# 添加项目根目录到Python路径，以便能够导入yys模块
sys.path.insert(0, str(Path("")))

# 确保工作目录是项目根目录
PROJECT_ROOT = Path(__file__).parent
os.chdir(PROJECT_ROOT)

app = FastAPI()

# 用于存储WebSocket连接
websocket_connections: Dict[str, WebSocket] = {}

# 心跳间隔时间（秒）
PONG_TIMEOUT = 30  # 30秒超时等待pong响应
HEARTBEAT_INTERVAL = 20  # 20秒发送一次心跳

# 任务执行相关变量
executor_thread: Optional[threading.Thread] = None
log_queue = queue.Queue()
input_queue = queue.Queue()
response_queue = queue.Queue()
pause_resume_event = threading.Event()
pause_resume_event.set()  # 默认为运行状态
current_task = None

# 手动注册任务
from yys.jiejietupo import JieJieTuPoScript
from yys.exploration import ExplorationScript
from yys.yuhun import YuHunScript
from yys.yuling import AutoYuling

TASKS: Dict[str, Type[YYSBaseScript]] = {
    "结界突破": JieJieTuPoScript,
    "探28": ExplorationScript,
    "御魂": YuHunScript,
    "御灵": AutoYuling
}


class UIStdin:
    """用于UI输入的stdin替代品"""

    def __init__(self, input_queue, response_queue):
        self.input_queue = input_queue
        self.response_queue = response_queue
        self.buffer = ""

    def readline(self):
        # 发送输入请求到UI
        self.input_queue.put("input_requested")
        # 等待UI响应
        response = self.response_queue.get()
        return response + "\n"

    def read(self, size=-1):
        line = self.readline()
        if size >= 0:
            return line[:size]
        return line

    def write(self, s):
        # stdin不应该有write方法，但以防万一
        pass


class TaskExecutor(threading.Thread):
    """任务执行器，在独立线程中运行脚本"""

    def __init__(self, task_name, task_class: Type[YYSBaseScript], log_queue, input_queue, response_queue):
        super().__init__()
        self.task_name = task_name
        self.task_class = task_class
        self.log_queue = log_queue
        self.input_queue = input_queue
        self.response_queue = response_queue
        self.original_cwd = os.getcwd()
        self.task_instance = self._instance_class()
        self.daemon = True

    def _instance_class(self):
        # 保存当前工作目录并在任务开始前切换到项目根目录
        logger.debug(f"当前工作目录: {self.original_cwd}")
        # 获取任务类所在的目录并切换
        task_module_path = os.path.dirname(inspect.getfile(self.task_class))
        logger.debug(f"任务类目录: {task_module_path}")
        os.chdir(task_module_path)
        # 创建任务实例
        return self.task_class()

    def run(self):
        """执行任务的主要方法"""
        original_stdin = sys.stdin
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        try:
            # 使用UIStdin替代stdin
            sys.stdin = UIStdin(self.input_queue, self.response_queue)

            # 重定向stdout到队列
            class StdoutRedirector:
                def __init__(self, log_queue):
                    self.log_queue = log_queue

                def write(self, text):
                    if text.strip():
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        self.log_queue.put({
                            "type": "log",
                            "data": f"[{timestamp}] {text.strip()}",
                            "level": "INFO"
                        })

                def flush(self):
                    pass

            sys.stdout = StdoutRedirector(self.log_queue)
            sys.stderr = StdoutRedirector(self.log_queue)
            # 运行任务
            self.task_instance.run()

            self.log_queue.put({
                "type": "log",
                "data": f"任务 {self.task_class.__name__} 执行完成",
                "level": "INFO"
            })

            # 发送任务完成状态
            self.log_queue.put({
                "type": "status",
                "data": "completed"
            })

        except Exception as e:
            self.log_queue.put({
                "type": "log",
                "data": f"任务执行出错: {str(e)}",
                "level": "ERROR"
            })
            import traceback
            self.log_queue.put({
                "type": "log",
                "data": f"错误详情: {traceback.format_exc()}",
                "level": "ERROR"
            })
            self.log_queue.put({
                "type": "status",
                "data": "error"
            })
        finally:
            # 恢复原始的stdin、stdout和 stderr
            sys.stdin = original_stdin
            sys.stdout = original_stdout
            sys.stderr = original_stderr

            # 恢复原来的工作目录
            os.chdir(self.original_cwd)

            self.log_queue.put({
                "type": "log",
                "data": "任务线程结束",
                "level": "INFO"
            })


    def pause(self):
        """暂停任务"""
        self.task_instance.pause()

    def resume(self):
        """恢复任务"""
        self.task_instance.resume()

    def stop(self):
        """停止任务"""
        self.task_instance.stop()


class TaskManager:
    """任务管理器，负责管理和提供注册的任务"""

    def __init__(self):
        self.tasks = self.load_registered_tasks()

    def load_registered_tasks(self):
        """从注册表加载任务"""
        tasks = {}
        for name, task_class in TASKS.items():
            tasks[name] = {
                'class': task_class,
                'description': f"{name} ({task_class.__doc__ or 'No description'})" if hasattr(task_class,
                                                                                               '__doc__') and task_class.__doc__ else name
            }
        return tasks


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # 将当前连接添加到连接池
    connection_key = f"ws_{len(websocket_connections)}"
    websocket_connections[connection_key] = websocket

    try:
        logger.debug(f"新连接已建立: {connection_key}")
        # 发送初始任务列表
        task_manager = TaskManager()
        tasks_data = []
        for name, info in task_manager.tasks.items():
            tasks_data.append({
                "name": name,
                "description": info['description']
            })

        await websocket.send_text(json.dumps({
            "type": "tasks",
            "data": tasks_data
        }))

        # 启动日志发送任务
        log_task = asyncio.create_task(send_logs_to_client(websocket))

        # 启动心跳任务
        heartbeat_task = asyncio.create_task(heartbeat(websocket, connection_key))

        # 处理WebSocket消息
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                logger.debug(f"收到消息: {message}")

                if message["type"] == "start_task":
                    task_name = message["task_name"]
                    task_manager = TaskManager()

                    if task_name in task_manager.tasks:
                        global executor_thread, current_task
                        if executor_thread and executor_thread.is_alive():
                            await websocket.send_text(json.dumps({
                                "type": "log",
                                "data": "已有任务在运行，请先停止当前任务",
                                "level": "ERROR"
                            }))
                            continue

                        task_class = task_manager.tasks[task_name]['class']
                        current_task = task_name

                        # 创建任务执行器
                        executor_thread = TaskExecutor(
                            task_name, task_class, log_queue,
                            input_queue, response_queue
                        )

                        # 启动任务
                        executor_thread.start()

                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "data": "running"
                        }))

                elif message["type"] == "pause_task":
                    if executor_thread and executor_thread.is_alive():
                        executor_thread.pause()
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "data": "paused"
                        }))

                elif message["type"] == "resume_task":
                    if executor_thread and executor_thread.is_alive():
                        executor_thread.resume()
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "data": "resumed"
                        }))

                elif message["type"] == "stop_task":
                    if executor_thread and executor_thread.is_alive():
                        executor_thread.stop()
                        executor_thread.join(timeout=3)
                        current_task = None

                    await websocket.send_text(json.dumps({
                        "type": "status",
                        "data": "stopped"
                    }))
                elif message["type"] == "input_response":
                    value = message["value"]
                    response_queue.put(value)
                    # 重置输入等待状态
                    waiting_for_input = False

            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket消息处理错误: {e}")
                break

            # 检查心跳状态
            if connection_key not in websocket_connections:
                break

    except WebSocketDisconnect:
        pass
    finally:
        # 从连接池中移除连接
        if connection_key in websocket_connections:
            del websocket_connections[connection_key]

        # 取消日志发送任务
        if 'log_task' in locals():
            log_task.cancel()


async def send_logs_to_client(websocket: WebSocket):
    """异步发送日志到客户端"""
    try:
        while True:
            try:
                # 获取日志消息
                try:
                    log_msg = log_queue.get_nowait()
                    logger.debug(f"下发日志消息：{log_msg}")
                    await websocket.send_text(json.dumps(log_msg))
                except queue.Empty:
                    pass

                await asyncio.sleep(0.1)  # 每100毫秒检查一次
            except Exception as e:
                print(f"发送日志时发生错误: {e}")
                await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        print("日志发送任务被取消")


async def heartbeat(websocket: WebSocket, connection_key: str):
    """WebSocket心跳机制，定期发送ping并等待pong响应"""
    try:
        last_pong_time = time.time()

        # 更新连接信息，包含最后心跳时间
        websocket.last_heartbeat = time.time()

        while True:
            # 发送ping消息
            await websocket.send_text(json.dumps({
                "type": "ping",
                "timestamp": int(time.time() * 1000)
            }))

            # 等待pong响应
            try:
                # 设置超时时间等待pong响应
                data = await asyncio.wait_for(websocket.receive_text(), timeout=PONG_TIMEOUT)
                message = json.loads(data)

                if message.get("type") == "pong":
                    last_pong_time = time.time()
                    websocket.last_heartbeat = last_pong_time
                    # 继续心跳循环
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
                else:
                    # 如果收到非pong消息，继续循环
                    continue
            except asyncio.TimeoutError:
                # 超时未收到pong响应，认为连接已断开
                print(f"心跳超时，连接 {connection_key} 已断开")
                break
            except WebSocketDisconnect:
                print(f"WebSocket连接 {connection_key} 断开")
                break
            except Exception as e:
                print(f"心跳处理异常: {e}")
                break

    except asyncio.CancelledError:
        print("心跳任务被取消")
    except Exception as e:
        print(f"心跳任务异常: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
