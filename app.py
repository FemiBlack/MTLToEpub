from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup, Doctype
from time import sleep
import traceback
import logging.config
import logging
import pypandoc
import json
import glob


logging.config.fileConfig('logging.ini', disable_existing_loggers=False)
logger = logging.getLogger(__name__)


def get_json_value(key, filename='nshba.json'):
    a_file = open(filename, "r")
    json_object = json.load(a_file)
    a_file.close()
    return json_object[key]


def update_json_file(value, filename='nshba.json'):
    a_file = open(filename, "r")
    json_object = json.load(a_file)
    a_file.close()

    # TODO edit this to loop over dictionary key-value pairs
    for key, value in value.items():
        json_object[key] = value

    a_file = open(filename, "w")
    json.dump(json_object, a_file)
    a_file.close()


def scroll_to_bottom(self, SCROLL_PAUSE_TIME=0.5):
    # Get scroll height
    last_height = self.browser.execute_script(
        "return document.body.scrollHeight")

    while True:
        # Scroll down to bottom
        self.browser.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);")

        # Wait to load page
        sleep(SCROLL_PAUSE_TIME)

        # Calculate new scroll height and compare with last scroll height
        new_height = self.browser.execute_script(
            "return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def write_json(new_data, filename='nshba.json'):
    with open(filename, 'r+') as file:
        # First we load existing data into a dict.
        file_data = json.load(file)
        # Join new_data with file_data inside emp_details
        file_data["all_chapters"].append(new_data)
        # Sets file's current position at offset.
        file.seek(0)
        # convert back to json.
        json.dump(file_data, file, indent=4)


def get_chapter_number(text):
    chapter_number = int(text.split(".")[1].split(" ")[0])
    return chapter_number

# wait = WebDriverWait(driver, 10)
# element = wait.until(EC.element_to_be_clickable((By.ID, 'someid')))


class Crawler:

    def __init__(self, url, starting_chapter, ending_chapter):
        logging.info("Crawler Initiated...")
        self.selected_chapters = []
        self.starting_chapter = starting_chapter
        self.ending_chapter = ending_chapter
        self.doc = BeautifulSoup()
        opts = Options()
        opts.add_argument("--headless")
        self.browser = Firefox(options=opts)
        try:
            self.browser.get(url)
        except:
            print(f"Connection error: Crawler Failed to get url: {url}")
            logger.error(
                f"Crawler Failed to get url: {url} - {traceback.format_exc()}")
            self.terminate_session()
            return None
        sleep(5)  # switch to explicit wait
        self.browser.find_element(
            By.XPATH, "/html/body/main/div[2]/div[1]/ul/li[2]").click()

    def crawl(self):
        try:
            self.populate_html()
        except:
            print("There was an error!")

    def get_chapters_in_range(self):
        print("Downloading html...")
        select = Select(self.browser.find_element(By.ID, 'pageSelector'))
        options = select.options
        selected_chapters = []
        keep_running = True
        overflow = False
        while keep_running:
            for index, opt in enumerate(options):
                lower, upper = opt.text.split("-")
                lower = int(lower)
                upper = int(upper)

                if ((lower <= self.starting_chapter <= upper) or overflow):
                    isLower = bool(lower <= self.starting_chapter <= upper)
                    print(lower, upper)
                    select.select_by_index(index)
                    sleep(1)

                    all_visible_chapters = self.browser.find_elements(
                        By.CLASS_NAME, "title-color")
                    chapter_index = abs(lower - self.starting_chapter) + 1
                    last_chapter_index = self.ending_chapter - upper
                    if isLower:
                        chapter_links = [chapter.get_attribute(
                            'href') for chapter in all_visible_chapters[chapter_index:]]
                        print("hit isLower")
                    elif (lower <= self.ending_chapter <= upper):
                        chapter_links = [chapter.get_attribute(
                            'href') for chapter in all_visible_chapters[1:last_chapter_index]]
                        print("hit max in range")

                    else:
                        chapter_links = [chapter.get_attribute(
                            'href') for chapter in all_visible_chapters[1:]]
                        print("hit still in progress")

                    selected_chapters += chapter_links
                    if ((lower >= self.ending_chapter) or (lower <= self.ending_chapter <= upper)):
                        overflow = False
                        keep_running = False
                        break

                    if self.ending_chapter > upper:
                        overflow = True
                        continue
        self.selected_chapters = selected_chapters
        # for i in self.selected_chapters:
        #     print(i)
        print("Downloaded %d chapters", len(self.selected_chapters))
        return selected_chapters

    def get_all_chapters(self):
        select = Select(self.browser.find_element(By.ID, 'pageSelector'))
        options = select.options
        for index, opt in enumerate(options):
            select.select_by_index(index)
            sleep(1)
            all_visible_chapters = self.browser.find_elements(
                By.CLASS_NAME, "title-color")
            update_json_file({"last_chapter": self.get_last_chapter()})
            for chapter in all_visible_chapters[1:]:
                chapter_metadata = {
                    "title": chapter.text,
                    "link": chapter.get_attribute('href')
                }
                write_json(chapter_metadata)

    def get_last_chapter(self):
        latest_chapter = self.browser.find_element(By.ID, "lastUpdate").text
        last_chapter = int(latest_chapter.split(".")[1].split(" ")[0])
        update_json_file({"last_chapter": self.get_last_chapter()})

        return last_chapter

    def terminate_session(self):
        self.browser.close()
        logging.info("Session terminated")
        print("Session terminated")

    def get_page_source(self, url):
        self.browser.get(url)
        sleep(1)
        return self.browser.page_source

    def construct_html(self, book_title="Nine Star Hegemon Body Art"):
        # Construct HTML skeleton
        self.doc.append(Doctype('html'))
        html = self.doc.new_tag('html', lang='en-US')
        self.doc.append(html)
        head = self.doc.new_tag('head')
        html.append(head)
        meta = self.doc.new_tag('meta', charset='utf-8')
        head.append(meta)
        title = self.doc.new_tag('title')
        title.string = book_title + \
            f"[{self.starting_chapter} - {self.ending_chapter}]"
        head.append(title)
        body = self.doc.new_tag('body')
        html.append(body)

    def populate_html(self):
        pages = self.get_chapters_in_range()
        self.construct_html()
        for index, page in enumerate(pages):
            page_source = self.get_page_source(page)
            self.construct_page_content(page_source, index)

        self.terminate_session()
        self.convert_to_epub()

    def convert_to_epub(self):
        epub_path = "downloads"
        print("Converting to epub...")
        pypandoc.convert_file('output.html', 'epub3',
                              outputfile=f"{epub_path}/Nine Star Hegemon Body Art Chapter {self.starting_chapter} - {self.ending_chapter}.epub")

    def construct_page_content(self, page_source, index):
        print(
            f"Constructing page content {self.starting_chapter+index}/{self.ending_chapter}....")
        # Gather each chapter's content
        page = BeautifulSoup(page_source, "lxml")
        # Construct h1 for the chapter
        header = self.doc.new_tag('h1')
        header.string = f"Chapter {self.starting_chapter+index} - {page.find(id='chapterContentTitle').text}"
        self.doc.body.append(header)

        # Load chapter content
        content = page.find(id='chapterContent')
        text_nodes = [e.strip()
                      for e in content if not e.name and e.strip()]
        for node in text_nodes:
            new_paragraph = self.doc.new_tag("p")
            new_paragraph.string = node
            self.doc.body.append(new_paragraph)

        # Append content between hr elements
        # hr_count = 0
        # for child in content.children:
        #     if child.name == 'ins':
        #         hr_count += 1
        #     elif child.name == 'p' and hr_count == 1:
        #         child.attrs = {}
        #         if child.string == '#':
        #             self.doc.body.append(self.doc.new_tag('hr'))
        #         else:
        #             self.doc.body.append(child)

        # Output final document
        # print(self.doc.prettify())
        with open("output.html", "w", encoding='utf-8') as file:
            # prettify the soup object and convert it into a string
            file.write(str(self.doc.prettify()))

# title = browser.find_element(By.ID, "chapterContentTitle")
# ads = browser.find_element(By.TAG, "ins")
# line_break = "<br>"


if __name__ == "__main__":
    BOOK_URL = "http://wnmtl.org/book/2290-nine-star-hegemon-body-art"

    last_chapter = get_json_value("last_chapter")
    print("NSHBA EPUB Parser v0.1")

    print("Here's a list of available epubs: ")
    epubs_in_cwd = glob.glob("*.epub")
    for index, epub in enumerate(epubs_in_cwd):
        print(f"{index+1} - {epub}")

    print(f"\nLatest Chapter: {last_chapter}")
    starting_chapter = int(
        input("Enter chapter number to begin download from: "))
    offset = int(input("Enter number of chapters to download: "))

    if(starting_chapter+offset > last_chapter):
        ending_chapter = last_chapter
    else:
        ending_chapter = starting_chapter+offset

    bot = Crawler(BOOK_URL, starting_chapter, ending_chapter)
    bot.crawl()
