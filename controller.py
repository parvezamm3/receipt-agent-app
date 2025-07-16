from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Callable, Any
try:
    from typing import NotRequired  # Python 3.11+
except ImportError:
    from typing_extensions import NotRequired  # For older Python versions
from dotenv import load_dotenv
import google.generativeai as genai
import os
import json
import re
import time
import sqlite3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from tools import (
    extract_and_crop_receipt_images,
    extract_data_from_images,
    evaluate_extracted_data_with_llm,
    manage_processed_receipt_files
)
from db_utils import receipt_exists, insert_failed_receipt, insert_success_receipt
from tools import _robust_move
import logging

logging.basicConfig(filename="info.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') 
logger = logging.getLogger(__name__)

load_dotenv()
# conn = sqlite3.connect("receipts.db")
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

DRIVE_PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__)) 
input_pdf_folder = os.path.join(DRIVE_PROJECT_FOLDER, "pdfs")
success_pdf_folder = os.path.join(DRIVE_PROJECT_FOLDER, "success_pdfs")
cropped_images_folder = os.path.join(DRIVE_PROJECT_FOLDER, "images")
error_pdf_folder = os.path.join(DRIVE_PROJECT_FOLDER, "error_pdfs")


RECEIPT_DATABASE_PATH = os.path.join(DRIVE_PROJECT_FOLDER, "receipts.db")

for _d in (input_pdf_folder, success_pdf_folder, error_pdf_folder, cropped_images_folder):
    os.makedirs(_d, exist_ok=True)

def stable_file(path: str, checks: int = 3, delay: float = 0.3) -> None:
    """Wait until a file reaches a stable size (handles partially‑written PDFs)."""
    last = -1
    for _ in range(checks):
        size = os.path.getsize(path)
        if size == last:
            return
        last = size
        time.sleep(delay)


def safe_replace(src: str, dst: str) -> None:
    """Cross‑platform atomic replace with fallback."""
    try:
        os.replace(src, dst)  # atomic on Win & POSIX (overwrites)
    except Exception:
        shutil.move(src, dst)

class GraphState(TypedDict):
    """
    Represents the state of our receipt processing workflow.
    Values are "patches" (updates to the state).
    """
    pdf_path: str
    image_paths: Annotated[list[str], "append"] # Use append to collect multiple paths
    extracted_json_str: NotRequired[str]
    evaluated_data: NotRequired[str]
    db_process_status: NotRequired[str]
    processed_status: NotRequired[str]  # "SUCCESS" | "FAILED"
    error_message: NotRequired[str]# "SUCCESS" or "FAILED"

def call_extract_images(state: GraphState) -> GraphState:
    """Node to extract and crop images from the PDF."""
    print("\n--- Node: call_extract_images ---")
    pdf_path = state["pdf_path"]
    try:
        result = extract_and_crop_receipt_images.invoke({
            "pdf_path": pdf_path,
            "cropped_images_folder": cropped_images_folder
        })
        if result.startswith("ERROR:"):
            return {"processed_status": "FAILED", "error_message": result} # type: ignore
        image_paths = list(json.loads(result).values())[0]
        return {
                "image_paths": image_paths,
                "processed_status": "SUCCESS"
            } # type: ignore
    except Exception as e:
        return {"processed_status": "FAILED", "error_message": f"Extract images failed: {e}"} # type: ignore
    
def call_extract_data(state: GraphState) -> GraphState:
    """Node to extract structured data from images using Gemini."""
    print("\n--- Node: call_extract_data ---")
    if state.get("processed_status") != "SUCCESS":
        return {"processed_status": "FAILED", "error_message": f"Extract data failed because of corrupted data"} # type: ignore
    try:
        result = extract_data_from_images.invoke({
            "image_paths_json_str": json.dumps(state["image_paths"])
        })
        if result.startswith("ERROR:"):
            return {"processed_status": "FAILED", "error_message": result} # type: ignore
        return {"extracted_json_str": result, "processed_status": "SUCCESS"} # type: ignore
    except Exception as e:
        return {"processed_status": "FAILED", "error_message": f"Extract data failed: {e}"} # type: ignore
    

def call_evaluate_data(state: GraphState) -> GraphState:
    """Node to evaluate the extracted data using another LLM."""
    if state.get("processed_status") != "SUCCESS":
        return {"processed_status": "FAILED", "error_message": f"Evaluating data failed because of corrupted data"} # type: ignore
    
    try:
        result = evaluate_extracted_data_with_llm.invoke({  # noqa: F821
            "extracted_json_str": state["extracted_json_str"], # type: ignore
            "original_pdf_path": state["pdf_path"],
        })
        if result.startswith("ERROR:"):
            return {"processed_status": "FAILED", "error_message": result} # type: ignore
        return {"evaluated_data": result, "processed_status": "SUCCESS"} # type: ignore
    except Exception as e:
        return {"processed_status": "FAILED", "error_message": f"LLM evaluation failed: {e}"} # type: ignore
    

def call_finalize(state: GraphState) -> GraphState:
    """Node to manage processed files."""
    print("\n--- Node: call_process_files ---")
    if state.get("processed_status") != "SUCCESS":
        return {"processed_status": "FAILED", "error_message": f"Finalize failed because of corrupted data"} # type: ignore
    try:
        evaluation = json.loads(state["evaluated_data"]) # type: ignore
        score = evaluation["evaluation_score"]
        feedback = evaluation["feedback"]
        # pdf_path = state["pdf_path"]
        pdf_filename = os.path.basename(state["pdf_path"])
        print(f"Pdf Filename: {pdf_filename},  Evaluation score: {score}, feedback: {feedback}")
        if score > 75:
            new_id = insert_success_receipt(pdf_filename, json.loads(state["extracted_json_str"]), feedback, score)
            validation_success = True
        else:
            error_msg = "評価スコアが低いため、処理に失敗しました。"
            new_id = insert_failed_receipt(pdf_filename, error_msg, json.loads(state["extracted_json_str"]),feedback, score)
            validation_success = False
        result = manage_processed_receipt_files.invoke({  # noqa: F821
            "original_pdf_path": state["pdf_path"],
            "cropped_images_folder": cropped_images_folder,
            "success_pdf_folder": success_pdf_folder,
            "error_pdf_folder": error_pdf_folder,
            "validation_success": validation_success,
            "new_file_name": new_id,
        })
        if result.startswith("ERROR:"):
            return {"processed_status": "FAILED", "error_message": result} # type: ignore
        return {"processed_status": "SUCCESS"} # type: ignore
    except Exception as e:
        return {"processed_status": "FAILED", "error_message": f"File management failed: {e}"} # type: ignore
    
workflow = StateGraph(GraphState)
workflow.add_node("extract_images", call_extract_images)
workflow.add_node("extract_data", call_extract_data)
workflow.add_node("evaluate_data", call_evaluate_data)
workflow.add_node("finalize", call_finalize)
workflow.set_entry_point("extract_images")

# Success path edges
workflow.add_edge("extract_images", "extract_data")
workflow.add_edge("extract_data", "evaluate_data")
workflow.add_edge("evaluate_data", "finalize")
workflow.add_edge("finalize", END)
app = workflow.compile()


def process_pdf(pdf_path: str):
    # Put your existing pipeline invocation here
    print(f"🛠️  Start processing {pdf_path}")
    pdf_filename = os.path.basename(pdf_path)
    if receipt_exists(pdf_path):
        print(f"{pdf_path} already processed — skipping")
        insert_failed_receipt(
            pdf_filename, "同じ名前のファイルは既に処理されています", {}, None, None,
        )
        _robust_move(pdf_path, os.path.join(error_pdf_folder, pdf_filename))
        return
        
    print(f"\n--- New PDF detected: {pdf_filename}. Starting LangGraph workflow. ---")

    initial_state = GraphState(
        pdf_path=pdf_path, # type: ignore
        image_paths=[],
    )

    try:
        stable_file(pdf_path) # type: ignore
        initial_state = GraphState(
            pdf_path=pdf_path, # type: ignore
            image_paths=[],
        )
        final_state : GraphState | None = None
        for step_state in app.stream(initial_state):
            print(f"Current state: {step_state}")
            final_state = step_state # type: ignore

        status = final_state["finalize"]["processed_status"] # type: ignore
        print(f"Final state: {final_state}")
        if status == "SUCCESS":
            print(f"\n--- Workflow completed SUCCESSFULLY for {pdf_filename} ---")
        else:
            error_message = final_state.get("error_message", "Unknown error") if final_state else "No state captured"
            print(f"\n--- Workflow FAILED for {pdf_filename}: {error_message} ---")
            safe_replace(pdf_path, os.path.join(error_pdf_folder, pdf_filename)) # type: ignore
    except Exception as e:
        print(f"\n--- Critical error for {pdf_filename}: {e} ---")
        safe_replace(pdf_path, os.path.join(error_pdf_folder, pdf_filename))
    print(f"✅ Finished {pdf_path}")


class PDFHandler(FileSystemEventHandler):
    def __init__(self, executor: ThreadPoolExecutor):
        self.executor = executor
        self.seen = set()

    def on_created(self, event):
        if event.is_directory or not event.src_path.lower().endswith(".pdf"):
            return
        if event.src_path in self.seen:
            return
        self.seen.add(event.src_path)
        # Submit PDF for processing in threadpool
        self.executor.submit(process_pdf, event.src_path)

from watchdog.events import FileCreatedEvent
def monitor_and_process_pdfs(input_dir):
    executor = ThreadPoolExecutor(max_workers=1)
    handler = PDFHandler(executor)
    observer = Observer()
    observer.schedule(handler, input_pdf_folder, recursive=False)
    observer.start()

    # Submit all existing PDFs on startup
    for fn in os.listdir(input_pdf_folder):
        full = os.path.join(input_pdf_folder, fn)
        if fn.lower().endswith(".pdf"):
            handler.on_created(FileCreatedEvent(full))
    print(f"📁 Monitoring folder: {input_dir}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        import sys
        print("🛑 Stopping monitor...")
        observer.stop()
        # observer.join()
        print("✅ Folder monitor exited cleanly.")
        sys.exit(0)

if __name__ == "__main__":
    monitor_and_process_pdfs(input_pdf_folder)