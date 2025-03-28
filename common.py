import logging
import os
import sys
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
import time
import hashlib
import re
import calendar
import datetime
import json


# 结果保存路径
def make_file_path(search_type, task):
    """
    :param search_type:搜索类型
    :param task: 返回教师以及之前的保存路径，年份之后再说
    :return:
    """
    # 三种搜索类型
    # "paper" 直接搜paper
    # "school-teacher" 搜老师，必须带有学校
    # "school-year-month" 搜学校，得按月来进行搜索
    try:
        if search_type == "paper":
            paper_title = task['paper_title']
            # 替换掉非法字符
            illegal_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            for char in illegal_chars:
                paper_title = paper_title.replace(char, '_')
            return os.path.join("downloads", f"{paper_title}")

        elif search_type == "school-teacher":
            return os.path.join("downloads", f"{task['school_id']}_{task['school_name']}",
                                f"{task['teacher_id']}_{task['teacher_name']}")

        elif search_type == "school-year-month":
            return os.path.join("downloads", f"{task['school_id']}_{task['school_name']}", f"{task["year"]}",
                                f"{task['month_key']}")
        else:
            logging.error(f"生成路径失败，{task}对应了未定义搜索类型")
            return False
    except:
        logging.error(f"生成路径失败，{task}遭遇未知错误")
        return False


def return_search_date(year, month_value = 0):
    """
    当只输入年时，返回概念的第一天至最后一天；
    当同时输入年和月份时，返回该年该月的第一天和最后一天
    :param year:
    :param month_value:
    :return: begin date & end date
    """
    if month_value:
        return (datetime.datetime(year, month_value, 1).strftime("%Y-%m-%d"),
                datetime.datetime(year, month_value,
                                  calendar.monthrange(year, month_value)[1]).strftime("%Y-%m-%d"))
    else:
        return (datetime.datetime(year, 1, 1).strftime("%Y-%m-%d"),
                datetime.datetime(year, 12, 31).strftime("%Y-%m-%d"))


# 显示进度
def show_progress(total, current):
    percent = 100 * current / total
    progress = "█" * int(percent / 10)
    sys.stdout.write(f"\r{percent:3.0f}%|{progress:<10}| {current}/{total}")
    sys.stdout.flush()


# 用于任务记录
class Check:
    """
    用于任务完成的标识和检查的类
    一、该任务所有的工作是否已经完成
    二、该任务系统提供的文件是否已经下载
    三、该搜索结果的子页面是否处理结束
    四、子页面:该搜索结果的子页面是否是否下载
    五、子页面：该搜索结果的子页面信息是否已经提取结束
    """

    # 用于标记任务是否完成
    @staticmethod
    def mark_task_finish_flag(file_save_path):
        """Create a flag in the path to mark the task as completed."""
        with open(os.path.join(file_save_path, 'completed.flag'), 'w', encoding='utf-8') as f:
            f.write('1')
        return True

    # 用于检查任务是否完成
    @staticmethod
    def check_task_finish_flag(file_save_path):
        """Check if the flag in the path to check if task has been searched."""
        return os.path.exists(file_save_path) and 'completed.flag' in os.listdir(str(file_save_path))

    # 用于标记论文item是否处理完成
    # @staticmethod
    # def mark_item_done(file_save_path, paper_id):
    #     with open(
    #             os.path.join(file_save_path, f'{paper_id}.flag'),
    #             'a+', encoding='utf-8') as file:
    #         file.write(paper_id)
    #         file.write('\n')
    #
    # # 用于检查论文item是否处理完成
    # @staticmethod
    # def check_item_done(file_save_path, paper_id):
    #     return os.path.exists(file_save_path) and f'{paper_id}.flag' in os.listdir(str(file_save_path))

    @staticmethod
    def mark_item_done(file_save_path, paper_id):
        with open(
                os.path.join(file_save_path, 'item_completed_records.flag'),
                'a+', encoding='utf-8') as file:
            file.write(paper_id)
            file.write('\n')

    @staticmethod
    def check_item_done(file_save_path, paper_id):
        records = set()
        try:
            with open(os.path.join(file_save_path, 'item_completed_records.flag'),
                    'r', encoding='utf-8') as file:
                for record in file.readlines():
                    records.add(record.replace('\n', ''))
            if paper_id in records:
                return True
            else:
                return False
        except:
            logging.error(f"检查{paper_id}是否已经处理过出错！可能是第一个搜索，flag文件还没建立，")
            return False



    # 用于搜索结果下载记录（每个任务下的每篇搜索文章）
    @staticmethod
    def check_item_subpage_downloaded(file_save_path, paper_id):
        if (
                os.path.exists(file_save_path) and f'{paper_id}.html' in os.listdir(str(file_save_path))
        ) and (
                os.path.exists(file_save_path) and f'{paper_id}.dat' in os.listdir(str(file_save_path))
        ):
            return True
        else:
            return False


    @staticmethod
    def check_all_items_from_search_results_json(file_save_path, n_record):
        records = set()
        with (open(os.path.join(file_save_path, 'search_results_information_got.json'), 'r', encoding='utf-8') as file):
            for record in file:
                item_dict = json.loads(record)
                if "nh" not in item_dict["论文唯一代码"]:
                    # 硕博论文去掉
                    records.add(item_dict["论文唯一代码"])
        if len(records) == n_record:
            return True
        else:
            return False


def roll_down(driver, fold=40):
    """
    Roll down to the bottom of the page to load all results
    """
    # fold 倍数或者次数，就是下移500，重复40次
    for i_roll in range(1, fold + 1):
        time.sleep(0.1)
        driver.execute_script(f'window.scrollTo(0, {i_roll * 50});')


# 遍历文件夹中的所有文件
def list_all_files(path):
    all_file_list = list()
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            all_file_list.append(file_path)
    return all_file_list


def keep_chinese_english_spaces(text):
    return re.sub(r'[^\sa-zA-Z\u4e00-\u9fa5]', '', text)


def keep_chinese_english_spaces_num_dot(text):
    return re.sub(r'[^\s\d.a-zA-Z\u4e00-\u9fa5]', '', text)


def decorator(func):
    """
    装饰器，作用就是看是否有返回值，没有就使得返回值取值为
    """

    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except:
            result = ""
        return result

    return wrapper


@decorator
def get_element_text(driver, match_condition):
    """
    应用装饰器
    """
    info = driver.find_element(
        By.XPATH, match_condition
    ).text
    return info


def get_text_excluding_children(drive_element):
    """

    :param drive_element:
    :return:
    """
    # 本层加子节点所有的文本
    parent_text = drive_element.text
    try:
        # 子节点所有的文本
        child_elements = drive_element.find_elements(By.XPATH, "./*")
        for child_element in child_elements:
            parent_text = parent_text.replace(child_element.text, '')
        return parent_text
    except NoSuchElementException:
        return parent_text
