import os
import fitz
from PIL import Image, ImageChops
import json
import shutil
from langchain_core.tools import tool
import google.generativeai as genai
import time

import io
from dotenv import load_dotenv
import logging
import errno

# Set up logging
logging.basicConfig(filename="info.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') 
logger = logging.getLogger(__name__)

load_dotenv()

# Configure genai. This will use GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_API_KEY
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)


def _resize_image_for_gemini(image, max_size=2000):
    """Resizes a PIL Image to a maximum dimension for Gemini's input limits."""
    width, height = image.size
    if max(width, height) > max_size:
        if width > height:
            new_width = max_size
            new_height = int(max_size * height / width)
        else:
            new_height = max_size
            new_width = int(max_size * width / height)
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return image

def _pixmap_to_pillow(pix: fitz.Pixmap) -> Image.Image:
    """Convert a PyMuPDF Pixmap to a Pillow Image safely for any colorspace."""
    png_bytes: bytes = pix.tobytes("png")          # universal
    return Image.open(io.BytesIO(png_bytes)).convert("RGB")

@tool
def extract_and_crop_receipt_images(pdf_path: str, cropped_images_folder: str) -> str:
    """
    Extracts images from a PDF, crops the main content area (receipt),
    and saves cropped images to the output folder.
    Returns a JSON string of {'pdf_filename': ['path/to/img1.png', 'path/to/img2.png', ...]}
    or an error message.
    """
    cropped_image_paths = []
    base_filename = os.path.splitext(os.path.basename(pdf_path))[0]

    if not os.path.exists(pdf_path):
        return f"ERROR: PDF file not found at {pdf_path}"
    if not os.path.isdir(cropped_images_folder):
        os.makedirs(cropped_images_folder, exist_ok=True) # Ensure folder exists

    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc, start=1):
            img = _pixmap_to_pillow(page.get_pixmap(dpi=300))

            # Automatic cropping of whitespace with padding
            bg = Image.new(img.mode, img.size, (255, 255, 255))
            bbox = ImageChops.difference(img, bg).getbbox()

            if bbox:
                padding = 20
                left, upper, right, lower = bbox
                img_width, img_height = img.size

                left = max(0, left - padding)
                upper = max(0, upper - padding)
                right = min(img_width, right + padding)
                lower = min(img_height, lower + padding)

                cropped_img = img.crop((left, upper, right, lower))
            else:
                cropped_img = img # No content detected, keep full page

            output_image_path = os.path.join(cropped_images_folder, f"{base_filename}_page_{page_num}.png")
            cropped_img.save(output_image_path)
            cropped_image_paths.append(output_image_path)

        doc.close()
        if not cropped_image_paths:
             return f"ERROR: No images were extracted from {pdf_path}. It might be empty or corrupted."

        return json.dumps({os.path.basename(pdf_path): cropped_image_paths})
    except Exception as e:
        return f"ERROR: Failed to extract and crop images from '{pdf_path}': {e}"
    

@tool
def extract_data_from_images(image_paths_json_str: str, model_name: str = "gemini-2.0-flash") -> str:
    """
    Extracts structured data from a list of receipt image paths using the Gemini API.
    Input must be a JSON string like '["path/to/img1.png", "path/to/img2.png"]'.
    Returns a JSON string of the extracted receipt data, or an error message.
    """
    try:
        image_paths = json.loads(image_paths_json_str)
        if not isinstance(image_paths, list):
            return "ERROR: Input image_paths_json_str must be a JSON list of strings."

        model = genai.GenerativeModel(model_name)
        prompt_parts = [
            """
            あなたは領収書のデータを抽出し、構造化するエキスパートAIアシスタントです。
            提供された領収書画像から以下の詳細を抽出してください。領収書は複数のページにわたる場合があります。
            すべてのページからの情報を単一のJSONオブジェクトに統合してください。フィールドが見つからない場合は「null」を使用します。
            出力は、JSONオブジェクト以外の余分なテキストやフォーマットを含まない、クリーンなJSONオブジェクトでなければなりません。

            抽出するフィールド:
            - "宛名" (Addressee): サービス/製品の受取人の名前。
            - "日付" (Date): 取引の日付。YYYYMMDD形式で指定してください。
            - "金額" (Amount): 取引の合計金額。数字のみ、カンマや通貨記号なしで返答してください。
            - "消費税" (Consumption Tax): 取引に関連する消費税額。数字のみ、カンマや通貨記号なしで返答してください。
            - "消費税率" (Consumption Tax Rate): 適用される消費税率。数字のみ、パーセント記号なしで返答してください。
            - "相手先" (Vendor): ベンダー情報。辞書形式 { "名前"(Name), "住所" (Address), "電話番号" (Phone Number) }。
            - "登録番号" (Invoice Registration Number): 日本のインボイス登録番号。
            - "摘要" (Description): 簡単な説明または品目の詳細。リスト形式 [[名前, 数量, 単価, 合計]]。
            - カテゴリ (Category): 内容に基づいて、交通費、食費、文具費のいずれかに分類してください。

            結果を単一の、クリーンなJSONオブジェクトとして出力してください。
            """
        ]

        image_parts = []
        for path in image_paths:
            if not os.path.exists(path):
                logger.info(f"Warning: Image file not found at {path}. Skipping.")
                continue
            try:
                img = Image.open(path)
                resized_img = _resize_image_for_gemini(img) # Use internal helper
                image_parts.append(resized_img)
            except Exception as e:
                return f"ERROR: Could not load or resize image {path}. Error: {e}"

        if not image_parts:
            return "ERROR: No valid images were successfully loaded for extraction."

        prompt_parts.extend(image_parts)
        response = model.generate_content(prompt_parts)
        logger.info(response.text)
        raw_text = response.text

        if raw_text.startswith("```json"):
            cleaned_text = raw_text.replace("```json", "", 1).strip()
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3].strip()
        else:
            cleaned_text = raw_text.strip()

        json_result = json.loads(cleaned_text)
        return json.dumps(json_result, ensure_ascii=False) # Return JSON string
    except json.JSONDecodeError as e:
        return f"ERROR: Gemini output not valid JSON. Raw: {raw_text[:200]}... Error: {e}"
    except Exception as e:
        return f"ERROR: Failed to extract data from images ({image_paths_json_str}): {e}"


@tool
def evaluate_extracted_data_with_llm(extracted_json_str: str, original_pdf_path: str, model_name: str = "gemini-2.5-flash") -> str:
    """
    Evaluates the quality of extracted receipt data using an LLM and provides a confidence percentage.
    Input is the extracted JSON string and the original PDF path (for context).
    Returns a JSON string containing {'evaluation_score': int, 'feedback': str} or an error message.
    """
    try:
        extracted_data = json.loads(extracted_json_str)
    except json.JSONDecodeError:
        return "ERROR: Input extracted_json_str is not a valid JSON string for evaluation."
    model = genai.GenerativeModel(model_name)
    # Construct a prompt for the LLM to evaluate the extracted data
    prompt = f"""
    You are an expert AI assistant tasked with evaluating the accuracy and completeness
    of structured data extracted from a receipt.

    Here is the extracted data in JSON format:
    {json.dumps(extracted_data, ensure_ascii=False, indent=2)}

    Please evaluate this extracted data based on the following criteria:
    1.  **Completeness**: Are all expected fields (日付, 金額, 消費税, 消費税率, 相手先) present?
    2. ** Format**: Are the values in the correct format (e.g., 日付 should be YYYYMMDD, 金額,消費税率,消費税率 should be numeric)?
    3.  **Accuracy**: Do the values seem correct and plausible (e.g., date format, amount is numeric)?
    4.  **Consistency**: Is the data consistent across fields (e.g., if a description lists items, does the total amount make sense)?
    5. ** Category check **: Based on the data extracted, does the category (交通費, 食費, 文具費) match the content?

    Based on your evaluation, provide a confidence score (an integer from 0 to 100)
    indicating how confident you are that this data is accurate and complete.
    Also, provide brief feedback on any potential issues or areas for improvement.

    Return your response as a JSON object with two fields:
    - "evaluation_score": (integer, 0-100) Your confidence score.
    - "feedback": (string) Your textual feedback in Japanese.
    """

    try:
        response = model.generate_content(prompt)
        # logger.info(response)
        raw_text = response.text.strip()

        # --- Added debugging logger.info and error handling ---
        # logger.info(f"--- Raw LLM Response ---:\n{raw_text}\n--- End Raw LLM Response ---")

        if not raw_text:
             return "ERROR: LLM returned an empty response."

        if raw_text.startswith("```json"):
            cleaned_text = raw_text.replace("```json", "", 1).strip()
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3].strip()
        else:
            cleaned_text = raw_text.strip()

        evaluation_result = json.loads(cleaned_text)
        # logger.info(evaluation_result)
        # --- End Added debugging logger.info and error handling ---

        if "evaluation_score" not in evaluation_result or "feedback" not in evaluation_result:
            return f"ERROR: LLM evaluation response missing required fields. Raw: {cleaned_text}"

        if not isinstance(evaluation_result["evaluation_score"], int) or not (0 <= evaluation_result["evaluation_score"] <= 100):
            return f"ERROR: LLM evaluation score is not a valid integer between 0 and 100. Raw: {cleaned_text}"

        return json.dumps(evaluation_result, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return f"ERROR: LLM evaluation output not valid JSON. Raw: {raw_text[:200]}... Error: {e}"
    except Exception as e:
        return f"ERROR: Failed to evaluate data with LLM for '{os.path.basename(original_pdf_path)}': {e}"

def generate_unique_receipt_id(cursor_obj, date_str_yymmdd, table_name):
    """Generates a unique YYMMDD_XXX receipt ID."""
    logger.info(f"Generating unique receipt ID for date {date_str_yymmdd} in table {table_name}")
    base_id = date_str_yymmdd
    cursor_obj.execute(f"SELECT generated_receipt_id FROM {table_name} WHERE generated_receipt_id LIKE '{base_id}_%' ORDER BY generated_receipt_id DESC LIMIT 1")
    last_id = cursor_obj.fetchone()

    if last_id:
        last_counter_str = last_id[0].split('_')[-1]
        try:
            last_counter = int(last_counter_str)
            next_counter = last_counter + 1
        except ValueError:
            # Fallback if parsing fails, start from 1
            next_counter = 1
    else:
        next_counter = 1

    return f"{base_id}_{next_counter:03d}"



def _robust_move(src: str, dst: str, attempts: int = 5, delay: float = 0.5):
    for i in range(attempts):
        try:
            return shutil.move(src, dst)
        except OSError as e:
            if e.errno == errno.EACCES and i < attempts - 1:
                time.sleep(delay)
                continue
            raise
@tool
def manage_processed_receipt_files(original_pdf_path:str, cropped_images_folder: str,
                                   success_pdf_folder: str, error_pdf_folder: str,
                                   validation_success: bool, new_file_name: str) -> str:
    """
    Renames the original PDF file based on extracted data, copies it to the output folder,
    and updates a master JSON log file.
    Input must include original_pdf_path and the extracted data as a JSON string.
    Returns 'SUCCESS:[new_filename]' or 'ERROR:[description]'.
    """
    try:
        dst_folder = success_pdf_folder if validation_success else error_pdf_folder
        dst_path = os.path.join(dst_folder, f"{new_file_name}.pdf")
        _robust_move(original_pdf_path, dst_path)
        if os.path.exists(cropped_images_folder):
            shutil.rmtree(cropped_images_folder)
        return f"SUCCESS: moved to {dst_path}"
    except Exception as exc:
        return f"ERROR: {exc}"
  