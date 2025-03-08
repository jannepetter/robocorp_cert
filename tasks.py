import shutil
from pathlib import Path
from robocorp.tasks import task
from robocorp import browser
from playwright.sync_api import expect
from RPA.HTTP import HTTP
from RPA.PDF import PDF
from RPA.Tables import Tables, Table

RETRIES = 15
TIMEOUT = 1000


@task
def order_robots_from_RobotSpareBin():
    """
    Orders robots from RobotSpareBin Industries Inc.
    Saves the order HTML receipt as a PDF file.
    Saves the screenshot of the ordered robot.
    Embeds the screenshot of the robot to the PDF receipt.
    Creates ZIP archive of the receipts and the images.
    """

    # browser.configure(
    #     slowmo=200,
    # )
    open_robot_order_website()
    close_annoying_modal()
    orders = get_orders()
    for order in orders:
        fill_the_form(order)

    archive_receipts()


def get_orders() -> Table:
    """
    Downloads csv file from the URL
    """

    http = HTTP()
    http.download(url="https://robotsparebinindustries.com/orders.csv", overwrite=True)
    reader = Tables()
    table = reader.read_table_from_csv("orders.csv")

    return table


def open_robot_order_website():
    """
    Navigates to the given URL
    """

    browser.goto("https://robotsparebinindustries.com/#/robot-order")


def close_annoying_modal():
    """
    Press ok and check modal is gone.
    """

    page = browser.page()
    for _ in range(RETRIES):
        try:
            page.get_by_role("button", name="OK").click()
            modal_btn = page.get_by_role("button", name="I guess so...")
            expect(modal_btn).not_to_be_visible(timeout=TIMEOUT)
            break
        except AssertionError:
            print("Modal still found, retrying...")


def fill_the_form(data):
    """
    Fill the form.
    """

    page = browser.page()
    page.select_option("#head", str(data["Head"]))
    page.click(f"#id-body-{data["Body"]}")
    page.get_by_placeholder("Enter the part number for the legs").fill(data["Legs"])
    page.get_by_placeholder("Shipping address").fill(data["Address"])
    page.get_by_role("button", name="Preview").click()

    for _ in range(RETRIES):
        try:
            page.get_by_role("button", name="Order").click()
            receipt = page.get_by_role("heading", name="Receipt")
            expect(receipt).to_be_visible(timeout=TIMEOUT)
            badge_text = page.locator("p.badge").text_content()
            pdf_path = store_receipt_as_pdf(badge_text)
            screenshot_path = screenshot_robot(badge_text)
            embed_screenshot_to_receipt(screenshot_path, pdf_path)
            break
        except AssertionError:
            print("Receipt not found, retrying...")
    else:
        print("Receipt did not appear in time!")

    page.get_by_role("button", name="Order another robot").click()

    close_annoying_modal()


def screenshot_robot(order_number) -> str:
    """
    Take screenshot.
    """

    page = browser.page()
    screenshot_path = f"output/screenshots/{order_number}.png"
    page.locator("#robot-preview-image").screenshot(path=screenshot_path)

    return screenshot_path


def store_receipt_as_pdf(order_number) -> str:
    """
    Store receipt.
    """

    page = browser.page()
    receipt = page.locator("#receipt").inner_html()

    pdf = PDF()
    pdf_path = f"output/receipts/{order_number}.pdf"
    pdf.html_to_pdf(receipt, pdf_path)

    return pdf_path


def embed_screenshot_to_receipt(screenshot, pdf_file):
    """Embed robot image to pdf."""

    pdf = PDF()
    pdf.add_watermark_image_to_pdf(
        image_path=screenshot, source_path=pdf_file, output_path=pdf_file
    )


def archive_receipts():
    """
    Archive all generated PDF receipts into a zip file.
    """

    pdfs_dir = Path("output/receipts")
    archive_path = shutil.make_archive("output/receipts_archive", "zip", pdfs_dir)

    return archive_path
