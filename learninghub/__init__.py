import re
import os
import math
import shutil
import subprocess
import logging

from fontTools.ttLib.woff2 import decompress
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from PyPDF2 import PdfFileMerger, PdfFileReader
import requests

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

def ebook2pdf_userpass(indexhtml, username, password, output_filename="ebook.pdf", output_dir=None, temp_dir=None, max_pages=1e6, logger=logger):
    """Generate PDF from a learninghub ebook. The ebook is accessed via
    username and password.

    Args:
        temp_dir (str): System path of directory where temporary files such as
            downloaded fonts and SVGs will be stored. Further subdirectories
            may be created. Directory must exist and must be empty (use one
            temporary directory per conversion).
    """

    logger.info(f"Create temporary directories under '{temp_dir}'.")
    screenshot_dir = f"{temp_dir}/screenshots"
    svg_dir = f"{temp_dir}/svgs"
    pdf_dir = f"{temp_dir}/pdfs"
    font_dir = f"{temp_dir}/fonts"
    os.mkdir(screenshot_dir)
    os.mkdir(svg_dir)
    os.mkdir(pdf_dir)
    os.mkdir(font_dir)

    cookies, num_pages = acquire_cookies_and_numpages(indexhtml, username, password, screenshot_dir=screenshot_dir, logger=logger)
    download_pages(indexhtml, cookies, min(num_pages, max_pages), svg_dir, logger=logger)
    download_webfonts_css(indexhtml, cookies, temp_dir, logger=logger)
    download_webfonts(indexhtml, cookies, f"{temp_dir}/webFonts.css", font_dir, logger=logger)
    generate_pdfs(svg_dir, font_dir, pdf_dir, logger=logger)
    concatenate_pdfs(pdf_dir, f"{output_dir}/{output_filename}", logger=logger)


def acquire_cookies_and_numpages(indexhtml, username, password, screenshot_dir=None, logger=logger):
    """Returns the cookies necessary to directly access a learninghub ebook's
    pages and font files. Additionally, returns the ebook's number of pages.

    The reason that these two different pieces of information are retrieved by
    a single function is that they require a live browser to access, and are
    thus acquired using selenium/webdriver inside a single session. The
    'screenshot_dir' parameter can be specified to take browser screenshots
    which are useful for post-crash debugging.

    Args:
        indexhtml (str): url of the ebook's 'index.html'
        username (str): username to use for learninghub.sap.com/login
        password (str): password to use for learninghub.sap.com/login
        screenshot_dir (str): system path to the screenshots' output directory.
            Directory must exist. If 'None' is passed, no screenshots will be
            taken.

    Returns:
        tuple(dict, int): a pair of a dictionary usable by the cookies
            parameter of requests by the requests library and the number of
            pages.
    """

    browser_options = Options()
    browser_options.add_argument("--headless")
    browser_options.add_argument("--no-sandbox")  # Required to run inside docker
    browser_options.add_argument("--disable-gpu")  # Required to run inside docker
    browser_options.add_argument("--disable-dev-shm-usage")  # Alternatively to this flag, map /dev/shm into the container.
    if screenshot_dir:
        browser_options.add_argument("window-size=2048x4096")  # Set a large window size for snapshots to capture all relevant content.
    driver = webdriver.Chrome(options=browser_options)
    driver.get("https://learninghub.sap.com/login")

    # Helper to take screenshots.
    snapshot_counter = 0
    if screenshot_dir:
        def take_snapshot():
            nonlocal snapshot_counter
            outfile_name = f"{snapshot_counter:03}.png"
            driver.save_screenshot(f"{screenshot_dir}/{outfile_name}")
            snapshot_counter += 1
    else:
        def take_snapshot():
            pass

    # NOTE: For the user and password fields we use
    #       'EC.element_to_be_clickable' over 'EC.presence_of_element_located'
    #       as the latter sometimes raises a 'ElementNotInteractableException'.
    logger.info("Enter username and confirm.")
    username_input = WebDriverWait(driver, timeout=90).until(
        EC.element_to_be_clickable((By.ID, "j_username"))
    )
    take_snapshot()
    username_input.send_keys(username)
    username_input.send_keys(Keys.RETURN)

    logger.info("Enter password and confirm.")
    password_input = WebDriverWait(driver, timeout=90).until(
        EC.element_to_be_clickable((By.ID, "password"))
    )
    take_snapshot()
    password_input.send_keys(password)
    password_input.send_keys(Keys.RETURN)

    logger.info("Click the 'Reject All' button.")
    reject_button = WebDriverWait(driver, timeout=90).until(
        EC.element_to_be_clickable((By.ID, "truste-consent-required"))
    )
    take_snapshot()
    reject_button.click()

    # Click on the "Browse content" link, which will eventually navigate to
    # 'saplearninghub.plateau.com' and will retrieve the cookies we need to access
    # the ebook's content itself.
    #
    # Clicking this link will open a new tab, which, for the sake of simplicity,
    # we circumvent by retrieving the link target and navigating there ourselves.
    logger.info("Click the 'Browse content' button.")
    browse_content_link = WebDriverWait(driver, timeout=90).until(
        # TODO: Find link by some property other than link text, as that could
        #       differ between users whose locales differ. This element has no Id.
        EC.element_to_be_clickable((By.LINK_TEXT, "Browse content"))
    )
    take_snapshot()
    target = browse_content_link.get_attribute("href")
    driver.get(target)
    WebDriverWait(driver, timeout=90).until(
        EC.presence_of_element_located((By.ID, "bizx-shared-header"))
    )
    take_snapshot()

    # We open the ebook's index.html in order to make sure that all cookies we
    # need are retrieved (it seems that get_cookies() does not return all
    # stored cookies by default).
    logger.info(f"Load the ebook's index.html: '{indexhtml}'.")
    driver.get(indexhtml)
    take_snapshot()

    logger.info("Export the cookies.")
    cookies = {c["name"]: c["value"] for c in driver.get_cookies()}  # format understood by requests package

    logger.info("Retrieve the number of pages.")
    pages_indicator = WebDriverWait(driver, timeout=90).until(
        EC.element_to_be_clickable((By.ID, "progressIndicator"))
    )
    num_pages = int(re.search("[0-9]+", pages_indicator.text)[0])  # text is slash followed by whitespace and the number of pages (e.g. '/ 450')

    logger.info("Close the Browser.")
    driver.quit()

    return cookies, num_pages


def download_pages(indexhtml, cookies, num_pages, output_dir, logger=logger):
    """Downloads an ebook's individual pages as SVG-files.

    Args:
        indexhtml (str): url of the ebook's 'index.html'
        cookies (dict): cookies required to access the ebook's resources
        num_pages (int): number of pages in the ebook
        output_dir (str): system path to the output directory. Directory must
            exist.

    Returns:
        None
    """
    logger.info("Download the ebook's pages as individual SVG files.")
    baseurl = indexhtml[:-11]
    padding = math.ceil(math.log10(num_pages))  # number of digits to pad to
    for ii in range(1, num_pages+1):
        url = f"{baseurl}/xml/topic{ii}.svg"
        logger.info(f"Download page {ii}/{num_pages}.")
        reply = requests.get(url, cookies=cookies)
        if reply.ok:
            with open(f"{output_dir}/{str(ii).rjust(padding, '0')}.svg", "w") as f:  # lpad filename with zeros
                f.write(reply.text)
        else:
            logger.warning(f"Error downloading ebook page {ii} from '{url}'. Skipping page.")


def download_webfonts_css(indexhtml, cookies, output_dir, logger=logger):
    """Downloads an ebook's 'webFonts.css' file.

    Args:
        indexhtml (str): url of the ebook's 'index.html'
        cookies (dict): cookies required to access the ebook's resources
        output_dir (str): system path to the output directory. Directory must
            exist.

    Returns:
        None
    """
    logger.info("Download webFonts.css.")
    baseurl = indexhtml[:-11]
    reply = requests.get(f"{baseurl}/css/webFonts.css", cookies=cookies)
    webfonts_css = reply.text
    with open(f"{output_dir}/webFonts.css", "w") as f:
        f.write(webfonts_css)


def download_webfonts(indexhtml, cookies, webfonts_css, output_dir, logger=logger):
    """Downloads fonts listed in the 'webFonts.css' file.

    Args:
        indexhtml (str): url of the ebook's 'index.html'
        cookies (dict): cookies required to access the ebook's resources
        webfonts_css (str): system path to the downloaded 'webFonts.css' file
        output_dir (str): system path to the output directory. Directory must exist.


    """
    logger.info("Extract the fonts' urls from webFonts.css.")
    baseurl = indexhtml[:-11]

    # match all .woff2 font files
    with open(webfonts_css, "r") as f:
        webfonts_css_str = f.read()
        font_paths = {e[5:-2] for e in re.findall(r"url\('[^')]+\.woff2'\)", webfonts_css_str)}

    logger.info(f"Download the ebook's required fonts (found {len(font_paths)} font URLs).")
    for font_path in font_paths:
        url = f"{baseurl}/css/{font_path}"
        reply = requests.get(url, cookies=cookies)
        if reply.ok:
            woff2_filename = font_path.split("/")[-1]
            with open(f"{output_dir}/{woff2_filename}", "wb") as f:
                f.write(reply.content)
            logger.info(f"Wrote '{woff2_filename}' to file.")
        else:
            logger.warning(f"Error downloading font from '{url}'. Skipping font.")


def generate_pdfs(svg_dir, font_dir, output_dir, logger=logger):
    """Generates PDFs from the ebook's individual SVG files.

    Args:
        pages_dir (str): system path to the directory containing the downloaded
            SVG files
        font_dir (str): system path to the directory containing the downloaded
            font files.
        output_dir (str): system path to the PDFs' output directory. Directory
            must exist.

    Returns:
        None
    """

    logger.info("Generate TTF fonts from downloaded WOFF2 fonts.")
    for woff2_filename in [f for f in os.listdir(f"{font_dir}") if f.endswith(".woff2")]:
        input_path = f"{font_dir}/{woff2_filename}"
        output_path = input_path[:-6] + ".ttf"
        decompress(input_path, output_path)

    fontconfig_dir = f"{os.getenv('HOME')}/.local/share/fonts"
    logger.info(f"Copy TTF fonts to fontconfig directory '{fontconfig_dir}'.")
    os.makedirs(fontconfig_dir, exist_ok=True)
    for ttf_filename in [f for f in os.listdir(f"{font_dir}") if f.endswith(".ttf")]:
        shutil.copy(f"{font_dir}/{ttf_filename}", fontconfig_dir, follow_symlinks=True)

    logger.info("Regenerate fontconfig cache.")
    result = subprocess.run(["fc-cache"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        logger.warning(f"Error regenerating fontconfig cache.\nstdout: {str(result.stdout, 'utf-8')}\nstderr: {str(result.stderr, 'utf-8')}")

    logger.info("Generate individual PDFs from the downloaded SVGs using inkscape.")
    for svg_filename in os.listdir(svg_dir):
        svg_path = f"{svg_dir}/{svg_filename}"
        pdf_filename = svg_filename.split(".")[0] + ".pdf"
        pdf_path = f"{output_dir}/{pdf_filename}"
        logger.info(f"Generating a PDF from file '{svg_path}'.")
        result = subprocess.run(["inkscape", f"--export-filename={pdf_path}", svg_path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            logger.warning(f"Error generating a PDF from file '{svg_path}'. Skipping file.\nstdout: {str(result.stdout, 'utf-8')}\nstderr: {str(result.stderr, 'utf-8')}")


def concatenate_pdfs(pdf_dir, output_path, logger=logger):
    """Concatenates individual PDF pages into a single PDF.

    Args:
        pdf_dir (str): system path to the directory containing the individual
            PDF pages. Its files will be concatenated in lexicographical order.
        output_path (str): system path of the output file. Base directory must
            exist.

    Returns:
        None
    """

    logger.info("Concatenate PDFs into a single document.")
    pdf_filenames = sorted(os.listdir(pdf_dir))
    pdf_paths = [f"{pdf_dir}/{pdf_filename}" for pdf_filename in pdf_filenames]
    pdf = PdfFileMerger()
    for pdf_path in pdf_paths:
        pdf.append(PdfFileReader(pdf_path, 'rb'))
    pdf.write(output_path)

    logger.info(f"Done: '{output_path}'")
