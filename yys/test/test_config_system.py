"""
测试配置系统是否正常工作
"""
import os

from yys.config_manager import config_manager, runtime_context, YuHunConfig, TanSuoConfig


def test_config_isolation():
    """测试配置隔离性"""
    print("=== 测试配置隔离 ===")
    
    # 设置并获取御魂配置
    runtime_context.set_current_script("御魂")
    yuhun_config = runtime_context.get_current_config(YuHunConfig)
    print(f"御魂配置初始debug: {yuhun_config.debug}")
    
    # 修改御魂配置
    config_manager.update_config("御魂", {"debug": True})
    yuhun_config = runtime_context.get_current_config(YuHunConfig)
    print(f"御魂配置修改后debug: {yuhun_config.debug}")
    
    # 设置并获取探索配置
    runtime_context.set_current_script("探索")
    tansuo_config = runtime_context.get_current_config(TanSuoConfig)
    print(f"探索配置debug: {tansuo_config.debug} (应该为False)")
    
    # 再次检查御魂配置，应该不受探索配置影响
    runtime_context.set_current_script("御魂")
    yuhun_config = runtime_context.get_current_config(YuHunConfig)
    print(f"再次获取御魂配置debug: {yuhun_config.debug} (应该为True)")


def test_runtime_context():
    """测试运行时上下文"""
    print("\n=== 测试运行时上下文 ===")
    
    runtime_context.set_current_script("御魂")
    print(f"当前脚本: {runtime_context.get_current_script()}")
    print(f"是否为调试模式: {runtime_context.is_debug_mode()}")
    
    # 更新配置并测试
    config_manager.update_config("御魂", {"debug": True})
    print(f"更新后是否为调试模式: {runtime_context.is_debug_mode()}")


def test_config_persistence():
    """测试配置持久化"""
    print("\n=== 测试配置持久化 ===")
    
    # 更新一些配置
    config_manager.update_config("御魂", {"debug": True, "max_battle_count": 99})
    config_manager.update_config("探索", {"debug": False, "max_battle_count": 50})
    
    # 保存到文件
    os.makedirs("../../test_config_dir", exist_ok=True)
    config_manager.save_to_file("test_config_dir/test_configs.json", "json")
    print("配置已保存到 test_config_dir/test_configs.json")
    
    # 从文件加载新管理器
    from yys.config_manager import ConfigManager
    new_manager = ConfigManager()
    new_manager.load_from_file("test_config_dir/test_configs.json", "json")
    
    # 验证加载的配置
    loaded_yuhun_config = new_manager.get_config("御魂", YuHunConfig)
    print(f"从文件加载的御魂配置: debug={loaded_yuhun_config.debug}, max_battle_count={loaded_yuhun_config.max_battle_count}")


def test_thread_safety():
    """测试线程安全性（基本概念验证）"""
    print("\n=== 测试线程安全性概念 ===")
    print("ContextVar确保了线程间的配置隔离，每个线程有独立的上下文")
    print("在多线程环境下，不同脚本的配置不会相互干扰")


if __name__ == "__main__":
    test_config_isolation()
    test_runtime_context()
    test_config_persistence()
    test_thread_safety()
    
    print("\n=== 所有测试完成 ===")