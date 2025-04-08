import shutil
from pathlib import Path
from robocorp.tasks import task
from robocorp import browser, workitems, vault, storage
from playwright.sync_api import expect
from RPA.HTTP import HTTP
from RPA.PDF import PDF
from RPA.Tables import Tables, Table
from cryptography.fernet import Fernet
import json
import base64

RETRIES = 15
TIMEOUT = 1000

# v0.1

# getting and setting assets as json
# asset = storage.get_json("test_asset")
# asset["oho"] = True
# storage.set_json("test_asset", asset)


def demo_encrypt_decrypt():
    """
    Demo for encrypt decrypt data and store it in the asset
    """
    data = {"name": "robot", "task": "encrypt", "status": True}

    key = "secretss" * 4  # 32 length required for Fernet

    print("key--", key)
    enc = encrypt_data(data, key)

    print("encrypted--", enc)
    storage.set_bytes("enc_asset", enc)

    data_from_storage = storage.get_bytes("enc_asset")

    dec = decrypt_data(data_from_storage, key)
    print("decrypted--", dec)


@task
def order_robots_from_RobotSpareBin():
    """
    Orders robots from RobotSpareBin Industries Inc.
    Saves the order HTML receipt as a PDF file.
    Saves the screenshot of the ordered robot.
    Embeds the screenshot of the robot to the PDF receipt.
    Creates ZIP archive of the receipts and the images.
    """
    demo_encrypt_decrypt()
    browser.configure(
        slowmo=200,
    )

    open_robot_order_website()
    close_annoying_modal()
    orders = get_orders()
    for order in orders:
        fill_the_form(order)

    archive_receipts()


# def user_input_task():
#     assistant = Assistant()
#     assistant.add_heading("Input from user")
#     assistant.add_text_input("text_input", placeholder="Please enter URL")
#     assistant.add_submit_buttons("Submit", default="Submit")
#     result = assistant.run_dialog()
#     url = result.text_input
#     print("printti--", url)
#     browser.goto(url)


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


def encrypt_data(data: dict, key: str) -> bytes:
    """
    Encrypt data.
    """
    key_bytes = base64.b64encode(key.encode("utf-8"))

    f = Fernet(key_bytes)
    data_bytes = json.dumps(data).encode("utf-8")
    encrypted_data = f.encrypt(data_bytes)

    return base64.b64encode(encrypted_data)


def decrypt_data(data_enc: bytes, key: str) -> dict:
    """
    Decrypt data.
    """
    key_bytes = base64.b64encode(key.encode("utf-8"))

    f = Fernet(key_bytes)
    decoded_bytes = base64.b64decode(data_enc)
    decrypted_bytes = f.decrypt(decoded_bytes)
    data = json.loads(decrypted_bytes)

    return data
