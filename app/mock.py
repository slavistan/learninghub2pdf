import time
import PyPDF2
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

def ebook2pdf_userpass_learninghub_noop(indexhtml, username, password, output_filename="ebook.pdf", output_dir=None, temp_dir=None, max_pages=1e6, logger=logger):
    """Mimicks the communication between the flask server and the client
    without sending any requests to the learninghub. A dummy output file is
    generated at the end which can be sent to the client.

    Used to test and develop the user interface. The signarure is identical to
    'ebook2pdf_userpass'.
    """

    logger.info("Create temporary directories under 'foo/bar/bar'.")
    logger.info("Enter username and confirm.")
    logger.info("Enter password and confirm.")
    logger.info("Click the 'Reject All' button.")
    logger.info("Click the 'Browse content' button.")
    logger.info(f"Load the ebook's index.html: '{indexhtml}'.")
    logger.info("Export the cookies.")
    logger.info("Retrieve the number of pages.")
    logger.info("Close the Browser.")
    logger.info("Download the ebook's pages as individual SVG files.")
    for pagenum in range(1, 10):
        logger.info(f"Download page {pagenum}/10.")
        time.sleep(0.3)
    logger.info("Download webFonts.css.")
    logger.info("Download the ebook's required fonts.")
    logger.info("Generate TTF fonts from downloaded WOFF2 fonts.")
    logger.info("Copy TTF fonts to fontconfig directory 'foo/bar'.")
    logger.info("Regenerate fontconfig cache.")
    logger.info("Generate individual PDFs from the downloaded SVGs using inkscape.")
    logger.info("Concatenate PDFs into a single document.")
    time.sleep(1)

    # Generate a synthetic output file.
    pdf = PyPDF2.PdfFileWriter()
    pdf.addBlankPage(219, 297)
    output_path = f"{output_dir}/{output_filename}"
    with open(output_path, "wb") as f:
        pdf.write(f)
    logger.info(f"Done: '{output_path}'")