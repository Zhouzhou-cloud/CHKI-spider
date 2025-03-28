import time
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
import pandas as pd
import json
from tenacity import retry_if_exception_message
import common
import logging
import math
import os
from selenium import webdriver
import copy
from fake_useragent import UserAgent

from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

# 无需安装chromedriver,使用webdriver_manger直接安转和管理，理论上只需要运行一次
# don't need to download the chromedriver again, instead use the webdriver_manger,
# it will download and manger automatically, and theoretically it needs to run only once
from webdriver_manager.chrome import ChromeDriverManager
# 配合webdriver_manger需要的函数
from selenium.webdriver.chrome.service import Service

check = common.Check()


def start_crawler(search_type, task, proxy):
    # 文件路径
    if not common.make_file_path(search_type=search_type, task=task):
        logging.debug("返回的是空路径")
        return False
    file_save_path = common.make_file_path(search_type=search_type, task=task)

    # 开始任务前准备
    # 看任务文件夹是否已经建立，即看是否是假的值，如果不是就继续，建立对应文件夹，不然用open with 时就会出错
    if file_save_path is not None:
        os.makedirs(file_save_path, exist_ok=True)
        logging.info(f"{file_save_path}文件夹已经建立")

    # 检查该任务是否已经完成，如果此任务没完成的话，开始此任务
    if file_save_path is not None and check.check_task_finish_flag(file_save_path):
        logging.info(f"{file_save_path}已经全部完成，无需再次进行！")
        return False

    # 必须得多次实例化，不然会被知网拒绝访问
    driver,current_ip = driver_login(proxy)
    if driver is False:
        logging.info(f"{file_save_path} 因没有足够有效的代理IP而无法启动")
        return False

    # 开始搜索
    if not search_query(driver=driver,search_type=search_type, task=task):
        # Stop if something goes wrong and quit the driver
        driver.quit()
        if proxy.mode == "no-school":
            # 检查代理ip是否还可用
            if proxy.validate_proxy(current_ip):
                # 释放锁
                proxy.release_a_proxy(current_ip)
        return False

    # 开始获取信息
    if not crawl_all_search_results_subpage(driver=driver,search_type=search_type, task=task):
        # 这里只有一种情况会return False
        driver.quit()
        if proxy.mode == "no-school":
            # 检查代理ip是否还可用
            if proxy.validate_proxy(current_ip):
                # 释放锁
                proxy.release_a_proxy(current_ip)
        return False

    # 最终成果了，也得关闭
    driver.quit()
    if proxy.mode=="no-school":
        # 释放锁
        proxy.release_a_proxy(current_ip)
    return True


def driver_login(proxy):

    # # get直接返回，不再等待界面加载完成
    # 这条命令似乎没有被使用
    # desired_capabilities = DesiredCapabilities.CHROME
    # desired_capabilities["pageLoadStrategy"] = "none"

    # 开始任务
    # options设定

    options = webdriver.ChromeOptions()
    options.add_argument("--disable-infobars")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    # 设置chrome不加载图片，提高速度
    options.add_experimental_option(
        "prefs", {"profile.managed_default_content_settings.images": 2}
    )

    # 去掉浏览器上的正在受selenium控制
    options.add_argument("--disable-blink-features=AutomationControlled")

    # 设置不显示窗口
    # options.add_argument("--headless")
    #
    # ua = UserAgent()
    # options.add_argument(f"user-agent={ua.random}")

    # 动态IP设置
    # 获得代理IP
    if proxy.mode == "no-school":
        if proxy.get_a_proxy() is None:
            return False,False
        current_ip = proxy.get_a_proxy()
        options.add_argument(f'--proxy-server={current_ip}')
    else:
        current_ip = None

    # options.add_argument(f'--proxy-server=210.77.19.127:7897')

    # service设定

    # 用ChromeDriverManager安装最新的driver
    # 每次都会去联网检查是否已经下载，会导致报错
    # service = Service(ChromeDriverManager().install())

    # 指定一个driver路径
    service = Service(executable_path=r"C:\Users\yunruxian\.wdm\drivers\chromedriver\win64\134.0.6998.90\chromedriver-win32/chromedriver.exe")

    # 实例化并运行程序
    driver = webdriver.Chrome(options=options, service=service)

    # 页面放大
    driver.maximize_window()
    return driver,current_ip


def search_query(driver, search_type, task):
    """
    Go to advanced search page, insert query into search frame and search the query.
    """
    # 结果保存路径
    file_save_path = common.make_file_path(search_type=search_type, task=task)

    # Close extra windows
    if not len(driver.window_handles) == 1:
        handles = driver.window_handles
        for i_handle in range(len(handles) - 1, 0, -1):  # traverse in reverse order
            # Switch to the window and load the page
            driver.switch_to.window(handles[i_handle])
            driver.close()
        driver.switch_to.window(handles[0])

    # Search query
    try:
        driver.get("https://kns.cnki.net/kns8/AdvSearch")
    except:
        logging.error("无法打开此网页，请检查是否网络出错或被封锁！")
        return False

    max_retry = 3
    retry_times = 0
    while True:
        try:
            # 三种搜索类型
            # "paper" 直接搜paper
            # "school-teacher" 搜老师，必须带有学校
            # "school-year-month" 搜学校，得按月来进行搜索
            if search_type == "paper":
                    driver.find_element(
                        By.XPATH,
                        '//div[@class="gradeSearch"]//input[@data-tipid="gradetxt-1"]',
                    ).send_keys(task["paper_title"])

            if search_type == "school-teacher":
                # 搜学校还是搜作者都是在作者检索里
                WebDriverWait(driver, 10).until(
                    expected_conditions.presence_of_element_located((By.XPATH, '//li[@name="authorSearch"]'))
                ).click()
                # 传入作者
                driver.find_element(
                    By.XPATH,
                    '//div[@class="authorSearch"]//input[@data-tipid="gradetxt-1"]',
                ).send_keys(task["teacher_name"])
                # 传入机构
                driver.find_element(
                    By.XPATH,
                    '//div[@class="authorSearch"]//input[@data-tipid="gradetxt-2"]',
                ).send_keys(task["school_name"])

            if search_type == "school-year-month":
                # 搜学校还是搜作者都是在作者检索里
                WebDriverWait(driver, 20).until(
                    expected_conditions.presence_of_element_located((By.XPATH, '//li[@name="authorSearch"]'))
                ).click()

                # 传入机构
                driver.find_element(
                    By.XPATH,
                    '//div[@class="authorSearch"]//input[@data-tipid="gradetxt-2"]',
                ).send_keys(task["school_name"])

                # 让日期组件可见
                js1 = "$('input[id=datebox0').removeAttr('readonly')"
                driver.execute_script(js1)
                js2 = "$('input[id=datebox1').removeAttr('readonly')"
                driver.execute_script(js2)

                # 传入日期
                driver.find_element(
                    By.XPATH,
                    '//div[@class="tit-date-box"]//input[@id="datebox0"]',
                ).clear()
                driver.find_element(
                    By.XPATH,
                    '//div[@class="tit-date-box"]//input[@id="datebox0"]',
                ).send_keys(task["start_search_time"])
                driver.find_element(
                    By.XPATH,
                    '//div[@class="tit-date-box"]//input[@id="datebox1"]',
                ).clear()
                driver.find_element(
                    By.XPATH,
                    '//div[@class="tit-date-box"]//input[@id="datebox1"]',
                ).send_keys(task["end_search_time"])

            # 点击搜索
            driver.execute_script("arguments[0].click();",
                                  driver.find_element(By.XPATH, "//input[@class='btn-search']"))
            logging.info("Click the search btn succeed")
            # 如果成功了，退出循环，继续以后操作
            break
        except:
            retry_times += 1
            if retry_times > max_retry:
                logging.error("尝试次数超过设定次数，此次搜索作废，之后再议")
                return False
            else:
                # Retry
                logging.debug("Search retrying")
        # Wait for the query page
    try:
        # 根据文章链接判断是否加载成功
        WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_element_located((By.CLASS_NAME, 'result-table-list')))
        return True
    except:
        # 没有搜索结果的其他情况
        # 1 这人没有论文
        # 2 其他报错
        try:
            # No results
            content=driver.find_element(By.XPATH, "//p[@class='no-content']").text
            if content == "抱歉，暂无数据，请稍后重试。" or content == " 暂无数据，请重新检索" or content == "暂无数据，请重新检索":
                logging.warning("没有搜索结果：抱歉，暂无数据，请稍后重试。")
            # Mark as completed
            # 没有搜索结果时的任务标记
            if file_save_path is not None:
                # 不标记了这里，好多出错了，明明能够搜出来，怀疑是网速问题
                # check.mark_task_finish_flag(file_save_path)
                pass
            return False
        except NoSuchElementException:
            # Search failed
            # driver.find_element(By.XPATH, '//div[contains(@class, "result-table-list")]')
            logging.error("其他情况出错")
            return False


def crawl_all_search_results_subpage(driver, search_type, task):
    """
    Open records as new subpages, download or parse subpages according to the setting.
    add a function: 将

    open each record as a new subpage
    deal with subpages(using function:process_windows();用windows是因为只处理已经打开的subpage,也就相当于桌,所以需要重复调用):
        download all subpages
        get_subpage_inf_wanted(整理页面内所有的信息)
    """
    # 结果保存路径
    if not common.make_file_path(search_type=search_type, task=task):
        logging.error(f"任务：({task}) 生产文件夹时出错！")
    file_save_path = common.make_file_path(search_type=search_type, task=task)
    time.sleep(0.5)
    # 计算有多少个子网页需要打开
    try:
        n_record = int(
            driver.find_element(
                By.XPATH, '//div[@id="countPageDiv"]/span/em'
            ).text.replace(',', '').strip(" "))
    except NoSuchElementException:
        logging.error("获取检索结果数量出错")
        return False

    # 如果有20条以上的搜索结果，就将每页显示条数改成50
    # 大概率必须现有点击，所以直接改属性让其显示不太行
    if n_record>=20:
        driver.find_element(By.XPATH, '//*[@id="perPageDiv"]/div/i').click()
        driver.find_element(By.XPATH, '//*[@id="perPageDiv"]/ul/li[3]/a').click()
        time.sleep(5)

    # 计算一共有多少页
    n_page = math.ceil(n_record / 50)
    try:
        assert n_page < 120, "Too many pages"
    except AssertionError:
        logging.warning(f"{task['school_name']}_{task['year']}的搜索结果太多了，达到了{n_record}条")

    logging.info(f'{n_record} records found, divided into {n_page} pages')

    # begin loop
    for i_page in range(n_page):
        # 拉到最下面
        common.roll_down(driver)
        # 当前浏览器有多少个窗口？等于1，否则出错
        # assert len(driver.window_handles) == 1, "Unexpected windows"

        # 搜索结果列表
        # find_elements的返回值是列表，如果没找到元素就是空列表
        # result_table_records的结果不可能为空
        result_table_records = driver.find_elements(
            By.XPATH, "//table[@class='result-table-list']/tbody/tr"
        )

        # 循环网页一页中的条目
        for record in result_table_records:
            while len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                driver.close()
            driver.switch_to.window(driver.window_handles[0])

            # 获得该条目的所有信息
            # 获取论文唯一标识码
            paper_id = record.find_element(By.XPATH,
                                           "./td[9]/a[@class='icon-collect' and @title='收藏']").get_attribute(
                "data-filename")

            # 看这个篇文章是不是之前就搞过了
            # 包括网页信息下载 和 信息抓取 ，如果已经完成，就跳过这条信息，继续循环
            if check.check_item_done(file_save_path, paper_id):
                logging.info(f"{paper_id}已经爬过啦！")
                continue
            # 否则就继续抓取其他在搜索结果页面的外部信息

            # 获得子网页的网址
            # 论文类型不同，子网页网址所在的位置不同
            database = record.find_element(By.XPATH, "./td[@class='data']/span").text
            if database == "期刊":
                # 论文名
                title = record.find_element(By.XPATH, "./td[@class='name']/a").text
                # 获得子网页的网址
                url = record.find_element(By.XPATH, "./td[@class='name']/a").get_attribute("href")
                # 状态 撤回或正常
                try:
                    status = record.find_element(By.XPATH, "./td[@class='name']/b[@class='cMarkSign']").text
                except NoSuchElementException:
                    status = "正常"
                # 是否有作者
                try:
                    author = record.find_elements(By.XPATH, "./td[@class='author']/a")
                    if not author:
                        logging.info(f"{paper_id}作者为空，跳过这一条结果1")
                        n_record = n_record - 1
                        continue
                except NoSuchElementException:
                    logging.info(f"{paper_id}作者为空，跳过这一条结果2")
                    n_record = n_record - 1
                    continue

            # elif database == "硕士" or database == "博士":
            #     title = record.find_element(By.XPATH, "./td[@class='name']/div/div/a").text
            #     url = record.find_element(By.XPATH, "./td[@class='name']/div/div/a").get_attribute("href")
            else:
                logging.error(f'不是期刊')
                n_record = n_record - 1
                continue

            # 获得信息（不需要进入子页面的信息）
            source = record.find_element(By.XPATH, "./td[@class='source']").text
            publish_date = record.find_element(By.XPATH, "./td[@class='date']").text
            try:
                quote = record.find_element(By.XPATH, "./td[@class='quote']/span").text
            except NoSuchElementException:
                quote = "0"
            try:
                download = record.find_element(By.XPATH, "./td[@class='download']/div/a").text
            except NoSuchElementException:
                download = "0"

            # 打开子页面，获得子页面内部的信息
            driver.execute_script(f'window.open(\"{url}\");')
            driver.switch_to.window(driver.window_handles[1])

            # 等待子页面加载完成/并强制暂停0.5秒
            try:
                WebDriverWait(driver, 20).until(
                    expected_conditions.presence_of_element_located(
                        (By.CLASS_NAME, "brief")
                    )
                )
            except TimeoutException:
                logging.error(f"{paper_id}加载子页面出错")
                driver.close()
                continue
            time.sleep(1)

            # 下载页面
            # 先检查页面是否已经下载，通过查看页面下载文件是否存在
            # if not check.check_item_subpage_downloaded(file_save_path, paper_id):
            #     if not download_item_subpage(driver, file_save_path, paper_id):
            #         logging.error(f"论文：({paper_id}) download mistake!")
            #         # 有错误就关闭
            #         driver.close()
            #         continue

            # 提取子页面内部独有的信息，直接在搜索结果里没有
            subpage_info = get_subpage_inf_wanted(driver, database, paper_id)
            if not subpage_info:
                logging.error(f"论文：({paper_id}) 子页面信息提取出错！")
                continue
            logging.info(f"论文：({paper_id}) 子页面信息提取完成！")
            # 不管成功还是失败，关闭，回到搜索页面，进行下一条
            driver.close()

            # 子页面信息和搜索结果信息整合，最终的结果信息
            if search_type == "paper":
                result_items = {
                    "论文类型": database,
                    "论文题目": title,
                    "状态": status,
                    "发表期刊": source,
                    "刊发时间": publish_date,
                    "引用量": quote,
                    "下载量": download,
                    "作者信息": subpage_info["作者"],
                    "年份": subpage_info["年份"],
                    "卷(Volume)": subpage_info["卷(Volume)"],
                    "期(Issue)": subpage_info["期(Issue)"],
                    "摘要": subpage_info["摘要"],
                    "关键词": subpage_info["关键词"],
                    "基金资助":subpage_info["基金资助"],
                    "专辑": subpage_info["专辑"],
                    "专题": subpage_info["专题"],
                    "分类号": subpage_info["分类号"],
                    "页码": subpage_info["页码"],
                    "页数": subpage_info["页数"],
                    "爬取时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                    "论文唯一代码": paper_id,
                }
            elif search_type == "school-teacher":
                result_items = {
                    "学校id": task["school_id"],
                    "学校": task["school_name"],
                    "学者id": task["teacher_id"],
                    "学者": task["teacher_name"],
                    "论文类型": database,
                    "论文题目": title,
                    "状态": status,
                    "发表期刊": source,
                    "刊发时间": publish_date,
                    "引用量": quote,
                    "下载量": download,
                    "作者信息": subpage_info["作者"],
                    "年份": subpage_info["年份"],
                    "卷(Volume)": subpage_info["卷(Volume)"],
                    "期(Issue)": subpage_info["期(Issue)"],
                    "摘要": subpage_info["摘要"],
                    "关键词": subpage_info["关键词"],
                    "基金资助":subpage_info["基金资助"],
                    "专辑": subpage_info["专辑"],
                    "专题": subpage_info["专题"],
                    "分类号": subpage_info["分类号"],
                    "页码": subpage_info["页码"],
                    "页数": subpage_info["页数"],
                    "爬取时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                    "论文唯一代码": paper_id,
                }
            elif search_type == "school-year-month":
                result_items = {
                    "学校id": task["school_id"],
                    "学校": task["school_name"],
                    "论文类型": database,
                    "论文题目": title,
                    "状态": status,
                    "发表期刊": source,
                    "刊发时间": publish_date,
                    "引用量": quote,
                    "下载量": download,
                    "作者信息": subpage_info["作者"],
                    "年份": subpage_info["年份"],
                    "卷(Volume)": subpage_info["卷(Volume)"],
                    "期(Issue)": subpage_info["期(Issue)"],
                    "摘要": subpage_info["摘要"],
                    "关键词": subpage_info["关键词"],
                    "基金资助":subpage_info["基金资助"],
                    "专辑": subpage_info["专辑"],
                    "专题": subpage_info["专题"],
                    "分类号": subpage_info["分类号"],
                    "页码": subpage_info["页码"],
                    "页数": subpage_info["页数"],
                    "爬取时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                    "论文唯一代码": paper_id,
                }
            else:
                logging.error(f"{task}的最终信息整理错误，请检查原因！")
                # 下一条，不然无法quit()
                continue
            # 存储该条目的所有信息
            if not save_result_info(result_items, file_save_path):
                logging.error(f"论文：({paper_id}) 保存信息是出错！")

            # mark一下该条论文已经全部处理完成
            check.mark_item_done(file_save_path, paper_id)
            logging.info(f"论文：({paper_id}) 子页面信息处理全部结束！")

        driver.switch_to.window(driver.window_handles[0])

        # Go to the next page
        if i_page + 1 < n_page:
            element = WebDriverWait(driver, 20).until(
                expected_conditions.element_to_be_clickable(
                    (
                        By.ID, "PageNext"
                    )))
            driver.execute_script("arguments[0].click();", element)
        # 等待加载完成
        WebDriverWait(driver, 20).until(
            expected_conditions.presence_of_element_located((By.CLASS_NAME, 'result-table-list')))

    # 根据下载的数据数目是否与查询到的数目对应，确定返回值
    if n_record == 0:
        check.mark_task_finish_flag(file_save_path)
        logging.info(f"{file_save_path}全是非期刊论文，结束!")
        return True
    else:
        ## 结果数量和搜索数量核对
        if  check.check_all_items_from_search_results_json(file_save_path, n_record):
            check.mark_task_finish_flag(file_save_path)
            logging.info(f"{file_save_path}已经全部处理结束!")
            return True
        else:
            logging.error("Record handled num does equate the num searched!")
            return False


def download_item_subpage(driver, file_save_path, paper_id):
    """
    Function of process_windows;Used for download the page
    """
    try:
        # Load the page or throw exception
        WebDriverWait(driver, 20).until(
            expected_conditions.presence_of_element_located((By.CLASS_NAME, 'brief')))

        # Download the record
        with open(os.path.join(file_save_path, f"{paper_id}.html"), 'w', encoding='utf-8') as file:
            file.write(driver.page_source)
            logging.debug(f'record # {paper_id} saved in {file_save_path}')

        # Download the record in dat
        with open(os.path.join(file_save_path, f"{paper_id}.dat"), 'w', encoding='utf-8') as file:
            file.write(driver.page_source)
            logging.debug(f'record # {paper_id} saved in {file_save_path}')
        return True
    except:
        logging.error(f"论文{paper_id}在下载时出错")
        return False


def get_subpage_inf_wanted(driver, database, paper_id):
    """
    爬取信息以下信息：论文名词，期刊，发表时间，作者，单位，类型，
    """
    # 现在只爬期刊，所以这里无所谓
    time.sleep(5)
    if database == "硕士" or database == "博士":
        student_name = driver.find_element(By.XPATH, "//*[@class='wx-tit']/h3[1]/span").text
        school = driver.find_element(By.XPATH, "//*[@class='wx-tit']/h3[2]/span").text
        authors_info = [dict(
            author_order=1,
            author_name=student_name,
            author_addresses=school,
            corresponding_author_label='NULL',
            corresponding_author_email='NULL',
        )]
        subpage_inf = {
            "作者": authors_info,
            "年份": "NULL",
            "卷(Volume)": "NULL",
            "期(Issue)": "NULL",
        }
        return subpage_inf
    elif database == "期刊":

        try:
            # 获得出版信息
            publish_data = driver.find_element(By.XPATH, "//*[@class='top-tip']/span/a[2]").text
            other, issue = publish_data.split('(')
            issue = issue.replace(")", "")
            if len(other.split(",")) == 2:
                publish_year, volume = other.split(",")
            else:
                publish_year = other
                volume = "No record"
        except:
            publish_year = ""
            volume = "No record"
            issue = "No record"

        # 获得作者及其单位院系信息
        authors_address_info=get_authors_address_info(driver,paper_id)
        if not authors_address_info:
            logging.error(f"论文：{paper_id}在获取作者信息时出错！")
            return False

        # 摘要
        abstract=""
        try:
            abstract = driver.find_element(By.XPATH, '//input[@id="abstract_text"]').get_attribute('value')
        except NoSuchElementException:
            logging.info(f"论文：{paper_id}无摘要！")
            pass
        # 关键词
        keywords=[]
        try:
            child_element = driver.find_element(By.XPATH, '//*[contains(text(), "关键词：")]')
            parent_element = child_element.find_element(By.XPATH, './..')
            keywords_elements = parent_element.find_elements(By.XPATH, './p/a')
            for funds_element in keywords_elements:
                keywords.append(funds_element.text.replace(";",""))
        except NoSuchElementException:
            logging.info(f"论文：{paper_id}无关键词！")
            pass

        # 基金资助
        funds=[]
        try:
            child_element = driver.find_element(By.XPATH, '//*[contains(text(), "基金资助：")]')
            parent_element = child_element.find_element(By.XPATH, './..')
            funds_elements = parent_element.find_elements(By.XPATH, './p/span')
            for funds_element in funds_elements:
                funds.append(funds_element.text.replace("；","").replace(";",""))
        except NoSuchElementException:
            logging.info(f"论文：{paper_id}无基金资助！")
            pass

        # 专辑
        special_issue = ""
        try:
            child_element = driver.find_element(By.XPATH, '//*[contains(text(), "专辑：")]')
            parent_element = child_element.find_element(By.XPATH, './..')
            special_issue = parent_element.find_element(By.XPATH, './p').text
        except NoSuchElementException:
            logging.info(f"论文：{paper_id}无专辑！")
            pass
        # 专题
        special_topic=""
        try:
            child_element = driver.find_element(By.XPATH, '//*[contains(text(), "专题：")]')
            parent_element = child_element.find_element(By.XPATH, './..')
            special_topic = parent_element.find_element(By.XPATH, './p').text
        except NoSuchElementException:
            logging.info(f"论文：{paper_id}无专题！")
            pass

        # 分类号
        class_code=""
        try:
            child_element = driver.find_element(By.XPATH, '//*[contains(text(), "分类号：")]')
            parent_element = child_element.find_element(By.XPATH, './..')
            class_code = parent_element.find_element(By.XPATH, './p').text
        except NoSuchElementException:
            logging.info(f"论文：{paper_id}无分类号！")
            pass

        # 页码
        page_from_end=""
        try:
            page_from_end = driver.find_element(By.XPATH, '//*[contains(text(), "页码：")]').text.replace("页码：","")
        except NoSuchElementException:
            logging.info(f"论文：{paper_id}无页码！")
            pass

        # 页数
        page_num=""
        try:
            page_num = driver.find_element(By.XPATH, '//*[contains(text(), "页数：")]').text.replace("页数：","")
        except NoSuchElementException:
            logging.info(f"论文：{paper_id}无页数！")
            pass

        subpage_inf = {
            "作者": authors_address_info,
            "年份": publish_year.strip(),
            "卷(Volume)": volume,
            "期(Issue)": issue,
            "摘要": abstract,
            "关键词": keywords,
            "基金资助":funds,
            "专辑": special_issue,
            "专题": special_topic,
            "分类号": class_code,
            "页码": page_from_end,
            "页数": page_num,
        }
        return subpage_inf


def  get_authors_address_info(driver,paper_id):
    """
    获得作者信息部分太长了，且可重复，所以单独设为一个函数
    """
    authors_info = []
    author_order = 1
    # 作者是span标签
    author_elements = driver.find_elements(
        By.XPATH,
        "//h3[@id='authorpart']/span"
    )
    if not author_elements:
        logging.error(f"{paper_id},在获取作者集时出错，文章疑似有问题，有可能没有作者")
        return False

    address_dict = get_address(driver, paper_id)
    if not address_dict:
        logging.error(f"{paper_id}获取地址时出错")
        return False

    # 就一个span的话，有三种情况
    # 1. 一个a标签一个作者 不带sup，就一个单位 eg:“东亚共同体”:地区与国家的观点
    # 2. 一个a标签一个作者 不带sup，多个单位 eg:试论利益集团在美国对华政策中的影响——以美国对华最惠国待遇政策为例
    # 3. 一个a标签一个作者 带sup, 有多个单位 eg:中美战略合作展望:对机遇与挑战前景的评估
    # 4. 一个text一个作者  eg:南疆行记
    # 5. 一个text多个作者，作者数目正好与有数字的单位数据对应 eg:偏振模色散对光纤数字通信系统影响的讨论
    # 6. 一个text多个作者，作者数目正好与有数字的单位数据对应，但邮政码（全数字）被当成了一个地址 eg:近年来CCA在气候分析与气候预测中的应用
    if len(author_elements) == 1:
        # 判断是否是a元素
        try:
            author_element= driver.find_element(
            By.XPATH,
            "//h3[@id='authorpart']/span/a"
            )
            # 获取姓名：下面可能有sup，所以用函数提出下面的子节点
            author_name = common.get_text_excluding_children(author_element)
            author_code = driver.find_element(
            By.XPATH,
            "//h3[@id='authorpart']/span/input"
            ).get_attribute("value")
            if not author_name:
                logging.error(f"论文：{paper_id}在获取a元素下姓名出错出错！")
                return False
            # 此时，只会有一个或者多个有序结果
            # 获取地址：无论是否有多个地址，以及有没有sup,都返回一个地址
            author_addresses=[]
            author_addresses_note=[]
            if len(address_dict) == 1:
                # 只有一个地址
                author_addresses.append(address_dict["onlyone"])
                author_addresses_note.append("单个a标签下单个单位：单个作者单个单位")
            else:
                for keys, value in address_dict.items():
                    author_addresses.append(value)
                author_addresses_note.append("单个a标签下多个单位：单个作者多个单位")
            author_info = dict(
                author_order=author_order,
                author_name=author_name,
                author_code=author_code,
                author_addresses=author_addresses,
                author_addresses_note=author_addresses_note,
                corresponding_author_label="No or unknown",
                corresponding_author_email="No record",
            )
            authors_info.append(author_info)
            # append()没有返回值，所以不能直接return
            return authors_info
        # 找不到a元素那就是text元素
        except NoSuchElementException:
            logging.info(f"{paper_id}没找到单一a要素，正转向单一text要素")
            try:
                author_names = driver.find_element(
                    By.XPATH,
                    "//h3[@id='authorpart']/span"
                ).text
            except NoSuchElementException:
                logging.info(f"{paper_id}单一text要素获取失败！")
                return False
            # 判别是几个作者
            if len(author_names.split(","))==1:
                # 就一个作者
                author_addresses=[]
                author_addresses_note=[]
                # 可能有多个地址
                if len(address_dict) == 1:
                    # 只有一个地址
                    author_addresses.append(address_dict["onlyone"])
                    author_addresses_note.append("单个text标签下单个单位：单个作者单个单位")
                else:
                    for keys, value in address_dict.items():
                        author_addresses.append(value)
                    author_addresses_note.append("单个text标签下多个单位：单个作者多个单位")
                author_info = dict(
                    author_order = author_order,
                    author_name = author_names,
                    author_code = "",
                    author_addresses = author_addresses,
                    author_addresses_note=author_addresses_note,
                    corresponding_author_label = "No or unknown",
                    corresponding_author_email = "No record",
                )
                authors_info.append(author_info)
                # append()没有返回值，所以不能直接return
                return authors_info
            else:
                # 多个作者
                for author_name in author_names.split(","):
                    # 如果能够得到有序的地址，就有序
                    # 返回值为False，或为字典
                    author_addresses=[]
                    author_addresses_note=[]
                    if len(author_names.split(","))==len(address_dict):
                        author_addresses.append(address_dict[f"{author_order}"])
                        author_addresses_note.append("单个text标签下多个作者多个单位，有序（数字）的单位,根据作者出现顺序与序号单位一一对应：多个作者多个单位，一一对应")
                    else:
                        for keys, value in address_dict.items():
                            author_addresses.append(value)
                        author_addresses_note.append("单个text标签下多个作者多个单位，有序（数字）的单位,但无法区别，堆集赋值：多个作者多个单位，堆集")
                    author_info = dict(
                        author_order=author_order,
                        author_name=author_name,
                        author_code="Null",
                        author_addresses=author_addresses,
                        author_addresses_note=author_addresses_note,
                        corresponding_author_label="No or unknown",
                        corresponding_author_email="No record",
                    )
                    authors_info.append(author_info)
                    author_order += 1
                return authors_info

    ## 此处需要考虑是否是通讯作者
    # 多个span有两种情况--肯定多个作者
    # 1 a标签带数字sup eg:如何认识负利率政策及其影响
    # 2 a标签不带数字sup 但单位只有一个：多作者同样单位 eg:数据生产要素的基础理论构建：新结构经济学视角
    # 3 a标签不带数字sup 单位有多个：可能多作者不同单位， eg:不同β受体阻滞剂对大鼠心肌间隙连接结构作用的对比研究;用于全口义齿计算机辅助设计的虚拟半可调架
    # 4 a标签不带数字sup 单位有多个：可能一一对一，正好单位数量等于作者数量；与3不好区分
    # 5 text
    else:
        for author_element in author_elements:
            # 多个span-多个作者循环
            author_addresses=[]
            author_addresses_note=[]

            # 作者姓名
            # span 套了 a, a下面可能套了sup；span直接套了text
            try:
                # 是否有a节点
                author_name_element = author_element.find_element(
                By.XPATH,
                './a'
                )
                # 通讯作者
                # 只有a节点下面会接sup和通讯作者
                corresponding_author, corresponding_author_email = corresponding_author_info(author_element)

                # a节点下面的作者名
                author_name = common.get_text_excluding_children(author_name_element)
                if not author_name:
                    logging.error(f"论文{paper_id}获取单一作者出错")
                    return False

                # input节点下的作者编号
                try:
                    author_code = author_element.find_element(
                        By.XPATH,
                        "./input"
                    ).get_attribute("value")
                except NoSuchElementException:
                    logging.error(f"论文{paper_id}下{author_name}没有作者编号属性！")
                    author_code="Null"

                # 作者对应单位序号
                # 检查下面是否套了sup
                # 需要注意的是作者单位序号和作者序号是不一样的。
                try:
                    address_orders = author_element.find_element(
                        By.XPATH,
                        './a/sup'
                    ).text.split(",")
                    # 可能获得一个值，也可能获得多个值
                    for address_order in address_orders:
                        author_addresses.append(address_dict[f"{address_order}"])
                        author_addresses_note=["多个span标签下多个作者,有序（数字）的单位,根据sup值一一对应：多个作者多个单位，一一对应"]
                    author_info = dict(
                        author_order=author_order,
                        author_name=author_name,
                        author_code=author_code,
                        author_addresses=author_addresses,
                        author_addresses_note=author_addresses_note,
                        corresponding_author_label=corresponding_author,
                        corresponding_author_email=corresponding_author_email,
                    )
                    authors_info.append(author_info)
                    author_order += 1
                    continue
                except NoSuchElementException:
                    # span节点下有a节点但没有sup节点
                    # 也就是多个span标签没有sup
                    if len(address_dict) == 1:
                        # 只有一个单位
                        author_addresses = address_dict["onlyone"]
                        author_addresses_note=["多个span标签下多个作者,一个单位：多个作者同样单位"]
                    else:
                        for key, value in address_dict.items():
                            author_addresses.append(value)
                            author_addresses_note=["多个span标签下多个作者，有序（数字）的单位,但没有sup可一一对应：多个作者多个单位，堆积"]
                    author_info = dict(
                        author_order=author_order,
                        author_name=author_name,
                        author_code=author_code,
                        author_addresses=author_addresses,
                        author_addresses_note=author_addresses_note,
                        corresponding_author_label=corresponding_author,
                        corresponding_author_email=corresponding_author_email,
                    )
                    authors_info.append(author_info)
                    author_order += 1
                    continue
            except NoSuchElementException:
                # span节点下没有a直接是作者text
                author_name = common.get_text_excluding_children(author_element)
                if not author_name:
                    logging.error(f"论文{paper_id}获取单一作者出错")
                    return False
                if len(author_elements) == len(address_dict):
                    author_addresses.append(address_dict[f"{author_order}"])
                    author_addresses_note=["单个text标签下多个作者多个单位，有序（数字）的单位,根据作者出现顺序与序号单位一一对应：多个作者多个单位，一一对应"]
                else:
                    for keys, value in address_dict.items():
                        author_addresses.append(value)
                        author_addresses_note=["单个text标签下多个作者多个单位，有序（数字）的单位,但无法区别，堆集赋值：多个作者多个单位，堆集"]

                    author_info = dict(
                        author_order=author_order,
                        author_name=author_name,
                        author_code="Null",
                        author_addresses=author_addresses,
                        author_addresses_note=author_addresses_note,
                        corresponding_author_label=[],
                        corresponding_author_email=[],
                    )
                    authors_info.append(author_info)
                    author_order += 1
                    continue
        return authors_info


def save_result_info(inf, file_save_path):
    try:
        # 写入txt
        # txt里好查看
        with open(os.path.join(file_save_path, 'search_results_information_got.txt'), 'a',
                  encoding='utf-8') as file:
            json.dump(inf, file, indent=4, ensure_ascii=False, allow_nan=True)
            file.write("\n")
        file.close()

        # 写入json
        with open(os.path.join(file_save_path, 'search_results_information_got.json'), 'a',
                  encoding='utf-8') as file:
            json.dump(inf, file, ensure_ascii=False, allow_nan=True)
            file.write("\n")
        file.close()
        return True
    except:
        logging.error(
            f"论文{inf["论文题目"]}：保存结果是出错！")
        return False

def get_address(driver,paper_id):
    """
    获取一个地址字典
    :param driver:
    :param paper_id:
    :return:
    """
    authors_address_dict=dict()
    """
    如果只有一个单位，name就是:
        {
        "onlyone":"address"
        }
    如果有多个单位，且有序号:
        {
        "1":"address"
        "2":"address"
        ...
        }
    如果有多个地址，但没有序号：
        {
        "noorder1":"address"
        "noorder2":"address"
        ...
        }
    """

    address_elements = driver.find_elements(
        By.XPATH,
        '//div[@class="wx-tit"]/h3[2]/span'
    )
    if not address_elements:
        logging.error(f"{paper_id}获取span地址列表错误,该文章没有单位地址")
        return False
    # 可能只有一个元素
    try:
        if len(address_elements)==1:
            for address_element in address_elements:
                authors_address_dict["onlyone"] = address_element.text
                return authors_address_dict
    except:
        logging.error(f"{paper_id}获取单一地址失败")
        return False
    # 用于计数
    n = 1
    try:
        # 有多个span，有可能有序号，有可能没有序号
        for address in address_elements:
            try:
                num, address_ture = address.text.split(".",maxsplit = 1)
                # 有序号数字被分离了出来
                if address_ture:
                    authors_address_dict[f"{num}"] = address_ture.split("!")[0]
            except:
                logging.debug( f"{paper_id}:用.分割序号和单位失败" )
                try:
                    num, address_ture = address.text.split(". ",maxsplit = 1)
                    # 有序号数字被分离了出来
                    if address_ture:
                        authors_address_dict[f"{num}"] = address_ture.split("!")[0]
                except:
                    logging.debug( f"{paper_id}:用. 分割序号和单位失败，可能没有序号" )
                    # 没有序号了
                    authors_address_dict[f"noorder{n}"] = address_elements.text.split("!")[0]
                    n += 1
    except:
        logging.debug(f"{paper_id}获取多个地址失败（包含有序和无序）")
        return False
    copy_authors_address_dict=copy.deepcopy(authors_address_dict)
    try:
        new_dict=dict()
        # 去掉都是数字（邮编）的字典
        keys=[]
        for key, value in authors_address_dict.items():
            if value.isdigit():
                keys.append(key)
        for key in keys:
            authors_address_dict.pop(key)
        # 一模一样，也就是没有value是全数字的错误
        if authors_address_dict==copy_authors_address_dict:
            return authors_address_dict
        else:
            # 修改pop掉错误单位地址后的字典的值
            new_order = 1
            for key, value in dict(sorted(authors_address_dict.items(), key=lambda x: x[0])).items():
                if key.isdigit():
                    new_dict[f"{new_order}"]=value
                else :
                    return authors_address_dict
                new_order += 1
            return new_dict
    except:
        logging.error("在去掉错误单位时出错")
        return False

def corresponding_author_info(author_element):
    # 通讯作者
    try:
        # 有通讯作者
        ele = author_element.find_element(
            By.XPATH,
            './a/i[@class="icon-email"]'
        )
        corresponding_author = "1"
        try:
            # 有通讯邮箱
            corresponding_author_email = author_element.find_element(
                By.XPATH,
                './p[@class="authortip"]'
            ).get_attribute('textContent')
        except:
            # 没有通讯邮箱
            corresponding_author_email = "No record"
    except:
        # 没有通讯作者
        corresponding_author = "No or unknown"
        corresponding_author_email = "No record"
    return corresponding_author, corresponding_author_email


def json_to_excel(file_path):
    """
    将下载的json数据转成excel
    """
    # 从json文件中加载数据
    # 读取JSON数据并解析为Python数据结构
    with open(os.path.join(file_path, 'search_results_information_got.json'), 'r', encoding='utf-8') as file:
        rows = []
        for line in file:
            data = json.loads(line)
            rows.append(data)

    # 将Python数据结构转换为DataFrame
    df = pd.json_normalize(rows)

    # 将DataFrame保存为Excel文件
    df.to_excel(os.path.join(file_path, 'search_results_information_got.xlsx'), index=False)


def combine_excel(path, output_filename="all_results.xlsx"):
    data_list = []
    # os.listdir(".")返回目录中的文件名列表
    for file in common.list_all_files(path):
        # 判断文件名以".xlsx"结尾
        if file.endswith("search_results_information_got.xlsx"):
            # pd.read_excel(filename)读取Excel文件，返回一个DataFrame对象
            # 列表名.append将DataFrame写入列表
            data_list.append(pd.read_excel(file))
        else:
            continue

    # concat合并Pandas数据
    data_all = pd.concat(data_list)
    # 将 DataFrame 保存为 excel 文件
    data_all.to_excel(output_filename, index=False)
