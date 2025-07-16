# Receipt Agent App

This project is a web application to manage and process receipts. It consists of a Python FastAPI backend and a React frontend.

## Setup & Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/ReceiptAgentApp.git
    cd ReceiptAgentApp
    ```

2.  **Backend Setup (Python/FastAPI):**
    *(From the project root directory)*
    ```bash
    # Create and activate a virtual environment
    python -m venv venv
    venv\Scripts\activate

    # Install dependencies
    pip install -r requirements.txt
    ```

3.  **Frontend Setup (React):**
    *(From the project root directory)*
    ```bash
    # Navigate to the UI directory
    cd receipt-ui

    # Install dependencies
    npm install
    ```

## Running the Application

You will need three separate terminals to run the Receipt Agent, backend and frontend servers.

1.  **Start the Recipt Agent:**
    *(In a terminal, from the project root directory)*
    If virtual enviroment is not activated
    ```bash
    venv\Scripts\activate
    ```
    ```bash
    python controller.py
    ```

2.  **Start the Backend Server:**
    *(In a new terminal, from `backend/api` directory)*
    Open a new terminal and activate the virtual environment and backend/api directory
    ```bash
    venv\Scripts\activate
    cd backend\api
    ```
    **Start the Flask Server**
    ```bash
    flask run
    ```
    The API will be running at `http://127.0.0.1:5000`.

3.  **Start the Frontend Development Server:**
    *(In a new terminal, from the `receipt-ui` directory)*
    ```bash
    # Navigate to the UI directory if you are not already there
    cd receipt-ui

    # Start the React development server
    npm run dev
    ```
    The application will be accessible at `http://localhost:5173` (or the port specified in the terminal).
