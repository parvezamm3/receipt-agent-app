# レシートエージェントアプリ

このプロジェクトは、レシートを管理および処理するためのWebアプリケーションです。Python FastAPIバックエンドとReactフロントエンドで構成されています。

## セットアップとインストール

1.  **リポジトリをクローンします:**
    ```bash
    git clone https://github.com/parvezamm3/recipe-agent-app.git
    cd ReceiptAgentApp
    ```

2.  **バックエンドのセットアップ (Python/FastAPI):**
    *(プロジェクトのルートディレクトリから)*
    ```bash
    # 仮想環境を作成してアクティブ化します
    python -m venv venv
    venv\Scripts\activate

    # 依存関係をインストールします
    pip install -r requirements.txt
    ```

3.  **フロントエンドのセットアップ (React):**
    *(プロジェクトのルートディレクトリから)*
    ```bash
    # UIディレクトリに移動します
    cd receipt-ui

    # 依存関係をインストールします
    npm install
    ```

## アプリケーションの実行

レシートエージェント、バックエンド、フロントエンドのサーバーを実行するには、3つの個別のターミナルが必要です。

1.  **レシートエージェントを開始します:**
    *(ターミナルで、プロジェクトのルートディレクトリから)*
    仮想環境がアクティブ化されていない場合
    ```bash
    venv\Scripts\activate
    ```
    ```bash
    python controller.py
    ```

2.  **バックエンドサーバーを開始します:**
    *(新しいターミナルで、`backend/api`ディレクトリから)*
    新しいターミナルを開き、仮想環境と`backend/api`ディレクトリをアクティブ化します
    ```bash
    venv\Scripts\activate
    cd backend\api
    ```
    **Flaskサーバーを起動します**
    ```bash
    flask run
    ```
    APIは`http://127.0.0.1:5000`で実行されます。

3.  **フロントエンド開発サーバーを開始します:**
    *(新しいターミナルで、`receipt-ui`ディレクトリから)*
    ```bash
    # UIディレクトリにまだいない場合は、そこに移動します
    cd receipt-ui

    # React開発サーバーを起動します
    npm run dev
    ```
    アプリケーションは`http://localhost:5173`（またはターミナルで指定されたポート）でアクセスできます。