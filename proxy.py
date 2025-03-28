import logging
import time
import requests
import random
import threading
from queue import Queue
from queue import Queue
from collections import defaultdict


class Proxy:
    """
    mode: school or no-school
    """
    def __init__(self,
                 mode,
                 filepath = "./proxypool/proxypool.txt",
                 check_url = "http://httpbin.org/ip",
                 ip_pool_min_size = 1
                 ):
        """
        初始化代理池
        :param check_url: 验证代理用的测试URL
        """
        self.mode = mode
        self.filepath = filepath
        self.check_url=check_url
        self.proxies = set()
        self.proxy_pool = Queue()
        self.lock = threading.RLock()
        self.ip_pool_min_size = ip_pool_min_size
        self.condition = threading.Condition()  # 条件变量（用于通知代理更新）

    def filter_proxies(self):
        """
        读取代理ip文件,并获得中国的
        """
        if self.mode == "no-school":
            # 过滤
            with (open(self.filepath,'r', encoding='utf-8') as file):
                for proxy in file.readlines():
                    if (
                            self.validate_proxy(proxy.replace('\n', ''))
                            and
                            self.__chinese_ip_check(proxy.replace('\n', ''))
                    ):
                        self.proxies.add(proxy.replace('\n', ''))
                        print(proxy.replace('\n', ''))
            # 保存
            with open(self.filepath, 'w', encoding='utf-8') as file:
                for proxy in self.proxies:
                    file.write(proxy)
                    file.write("\n")

        else:
            return True

    def validate_proxy(self, proxy):
        if self.mode == "no-school":
            try:
                response = requests.get(
                    self.check_url,
                    proxies={"http": proxy, "https": proxy},
                    timeout=10
                )
                if response.json()['origin'] == proxy.split(':')[0]:
                    return True
            except:
                return False
        else:
            return "school"

    def __chinese_ip_check(self, proxy):
        # 检查ip地址是否是中国
        try:
            if requests.get(f'http://ip-api.com/json/{proxy.split(":")[0]}').json().get('country', '')=="China":
                return True
            else:
                return False
        except:
            return False

    def init_proxy_pool(self):
        if self.mode == "no-school":
            # 读取
            with open(self.filepath, 'r', encoding='utf-8') as file:
                for proxy in file.readlines():
                    self.proxy_pool.put(proxy.replace('\n', ''))
        else:
            return "school"

    def get_a_proxy(self):
        """
        :return:
        """
        if self.mode == "no-school":
            # 取出代理前先检查代理ip是否充足
            with self.condition:
                # 如果代理池不足，触发补充
                while self.proxy_pool.qsize() < self.ip_pool_min_size:
                    logging.error("代理ip不足5个了")
                    return None

                # 取出代理
                with self.lock:
                    return self.proxy_pool.get()
        else:
            return "school"


    def release_a_proxy(self, proxy):
        if self.mode == "no-school":
            with self.lock:
                self.proxy_pool.put(proxy)
        else:
            return "school"
