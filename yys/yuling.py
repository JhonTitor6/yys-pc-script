from auto_script_base import YYSAutoScript


class AutoYuling(YYSAutoScript):
    def __init__(self):
        super().__init__("御灵", "images/yuling_tiaozhan.bmp")


if __name__ == '__main__':
    AutoYuling().run()
