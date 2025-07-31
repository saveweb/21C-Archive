import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import time

# ==================== 配置参数 ====================
# 可根据需要修改以下参数

# 期刊范围设置
START_ISSUE = 191  # 开始期刊号
END_ISSUE = 191    # 结束期刊号

# 网站URL设置
BASE_URL = "https://www.cuhk.edu.hk/ics/21c/zh/issues/back.html"

# 下载设置
REQUEST_TIMEOUT = 30     # 请求超时时间（秒）
DELAY_BETWEEN_FILES = 1  # 文件间下载延迟（秒）
DELAY_BETWEEN_ISSUES = 2 # 期数间下载延迟（秒）
DELAY_BETWEEN_YEARS = 1  # 年份页面间延迟（秒）

# 文件夹命名格式
FOLDER_NAME_FORMAT = "第 {issue_num} 期"  # {issue_num} 会被替换为实际期数

# 文件命名格式
FILE_NAME_FORMAT = "{counter}.{title}.pdf"  # {counter} 为编号，{title} 为标题

# ==================== 程序代码 ====================

def get_year_links(back_url):
    """获取所有年份页面的链接"""
    response = requests.get(back_url)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    year_links = []
    # 查找年份链接，通常格式为 y23y25.html
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if re.match(r"y\d+y\d+\.html", href):
            year_url = urljoin(back_url, href)
            year_links.append(year_url)

    return year_links

def get_issue_links(year_url):
    """从年份页面获取所有期数链接"""
    response = requests.get(year_url)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    issue_links = []
    # 查找期数链接，格式为 c195.html
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if re.match(r"c\d+\.html", href):
            issue_url = urljoin(year_url, href)
            # 提取期数
            issue_num = int(re.search(r"c(\d+)\.html", href).group(1))
            if START_ISSUE <= issue_num <= END_ISSUE:  # 使用配置的期刊范围
                issue_links.append((issue_num, issue_url))

    return issue_links

def download_pdfs_from_issue(issue_num, issue_url):
    """下载指定期数的所有PDF文件"""
    # 使用配置的文件夹命名格式
    folder_name = FOLDER_NAME_FORMAT.format(issue_num=issue_num)
    os.makedirs(folder_name, exist_ok=True)

    print(f"\n正在处理第 {issue_num} 期...")

    # 获取网页内容
    try:
        response = requests.get(issue_url)
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"无法访问期数页面 {issue_url}: {e}")
        return

    # 找到所有的 PDF 链接和对应的标题
    downloaded_count = 0
    file_counter = 1  # 添加文件计数器

    # 方法1: 尝试查找文章链接
    article_links = soup.find_all("a", href=True)
    for a in article_links:
        href = a.get("href", "")
        if href.endswith(".pdf"):
            pdf_url = urljoin(issue_url, href)

            # 尝试多种方式获取标题
            title = None

            # 方法1: 从链接文本获取
            if a.get_text(strip=True):
                title = a.get_text(strip=True)

            # 方法2: 从父元素或兄弟元素查找标题
            if not title or title in ["PDF", "下载", "查看"]:
                # 查找前面的标题元素
                title_elements = a.find_previous_siblings() + [a.parent]
                for elem in title_elements:
                    if elem and elem.get_text(strip=True):
                        potential_title = elem.get_text(strip=True)
                        if len(potential_title) > 5 and potential_title not in ["PDF", "下载", "查看"]:
                            title = potential_title
                            break

            # 方法3: 从URL中提取可能的标题信息
            if not title:
                title = f"文章_{file_counter}"

            # 清理标题，移除不安全字符
            safe_title = "".join(c for c in title if c not in r'\/:*?"<>|').strip()
            if not safe_title:
                safe_title = f"文章_{file_counter}"

            # 使用配置的文件命名格式
            filename = FILE_NAME_FORMAT.format(counter=file_counter, title=safe_title)
            filepath = os.path.join(folder_name, filename)

            # 检查是否已存在相同编号的文件（避免重复下载）
            existing_files = [f for f in os.listdir(folder_name) if f.startswith(f"{file_counter}.") and f.endswith(".pdf")]
            if existing_files:
                print(f"  文件已存在，跳过: {file_counter}.{safe_title}")
                file_counter += 1
                continue

            # 下载 PDF 文件
            try:
                print(f"  正在下载: {file_counter}.{safe_title}")
                pdf_response = requests.get(pdf_url, timeout=REQUEST_TIMEOUT)
                pdf_response.raise_for_status()

                with open(filepath, "wb") as f:
                    f.write(pdf_response.content)

                downloaded_count += 1
                print(f"  下载完成: {file_counter}.{safe_title}")

                # 使用配置的延迟时间
                time.sleep(DELAY_BETWEEN_FILES)

            except Exception as e:
                print(f"  下载失败 {file_counter}.{safe_title}: {e}")

            file_counter += 1  # 无论下载成功或失败都递增计数器

    print(f"第 {issue_num} 期完成，共下载 {downloaded_count} 个文件")

def main():
    """主函数：下载指定范围期数的所有PDF"""
    print(f"开始下载第 {START_ISSUE} 期到第 {END_ISSUE} 期的PDF文件...")
    print("开始获取年份页面链接...")
    year_links = get_year_links(BASE_URL)
    print(f"找到 {len(year_links)} 个年份页面")

    all_issues = []

    # 从所有年份页面收集期数链接
    for year_url in year_links:
        print(f"正在处理年份页面: {year_url}")
        try:
            issues = get_issue_links(year_url)
            all_issues.extend(issues)
            time.sleep(DELAY_BETWEEN_YEARS)  # 使用配置的延迟
        except Exception as e:
            print(f"处理年份页面失败 {year_url}: {e}")

    # 按期数排序
    all_issues.sort(key=lambda x: x[0])

    print(f"\n找到符合条件的期数 ({START_ISSUE}-{END_ISSUE}期): {[issue[0] for issue in all_issues]}")

    # 下载每一期的PDF
    for issue_num, issue_url in all_issues:
        try:
            download_pdfs_from_issue(issue_num, issue_url)
            time.sleep(DELAY_BETWEEN_ISSUES)  # 使用配置的延迟
        except Exception as e:
            print(f"处理第 {issue_num} 期失败: {e}")

    print(f"\n所有下载任务完成！共处理 {START_ISSUE}-{END_ISSUE} 期")

if __name__ == "__main__":
    main()
