import unittest


class TestPicAndColorUtil(unittest.TestCase):
    def test_json(self):
        with open(r'D:\Program Files\yys_20250620\Documents\cache_server_data\5b51ac6200291e985337c4ea\inventory', 'r') as f:
            hex_str = f.read()
        json_str = bytes.fromhex(hex_str).decode('utf-8')
        import json
        data = json.loads(json_str)
        print(data)


    def test_new_client_config(self):
        with open(r'D:\Program Files\yys_20250620\Documents\cache_server_data\5b51ac6200291e985337c4ea\new_client_config', 'r') as f:
            hex_str = f.read()
        json_str = bytes.fromhex(hex_str).decode('utf-8')
        import json
        data = json.loads(json_str)
        print(data)