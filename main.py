from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import logging
import tqdm
import crawl
from common import *
import make_task_list
from proxy import Proxy


"""setting"""

"""任务文件路径"""
task_file_path = "raw data file/第一批次.xlsx"

# Init
"""设置logging"""
os.makedirs('python file/logs', exist_ok=True)
logging.basicConfig(level=logging.INFO,
                    filename=os.getcwd() + '/logs/log' + time.strftime('%Y%m%d%H%M',
                                                                       time.localtime(time.time())) + '.log',
                    filemode="w",
                    format="%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s",
                    encoding="utf-8",
                    )

if __name__ == "__main__":

    # 实例化代理ip池类
    # proxy = Proxy(mode="no-school")

    proxy = Proxy(mode="school")

    if proxy.mode == "no-school":
        # # 筛选代理ip
        # proxy.filter_proxies()
        # 初始化线程代理ip锁
        proxy.init_proxy_pool()

    if not make_task_list.make_task_list(task_file_path):
        logging.error(f"未获得返回任务列表")

    search_type, task_list = make_task_list.make_task_list(task_file_path)

    # # 单线程
    # for task in task_list:
    #     crawl.start_crawler(search_type, task, proxy)
    #
    # 多线程加速
    threader = ThreadPoolExecutor(max_workers=5)
    remaining_tasks = []
    # Start Query
    # tqdm.tqdm(task_list)生成一个由迭代对象组成的进度条
    # 多线程命令
    for task in tqdm.tqdm(task_list):
        future = threader.submit(crawl.start_crawler, search_type, task, proxy)
        remaining_tasks.append(future)

    # 线程计数
    while True:
        for future in remaining_tasks:
            if future.done():
                remaining_tasks.remove(future)
        show_progress(len(task_list), (len(task_list) - len(remaining_tasks)))
        # 所有任务完成时就退出循环
        if len(remaining_tasks) == 0:
            break

    # trans form json to excel
    for task in tqdm.tqdm(task_list):
        # 结果保存路径
        file_save_path = make_file_path(task)

        if os.path.join(file_save_path, 'search_results_information_got.xlsx'
        ) not in os.listdir(
            file_save_path
        ):
            try:
                crawl.json_to_excel(file_save_path)
            except:
                continue

    crawl.combine_excel("downloads", output_filename="result_All.xlsx")


