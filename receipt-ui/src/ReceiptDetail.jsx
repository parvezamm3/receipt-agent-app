import { useParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import pdfWorkerURL from "pdfjs-dist/build/pdf.worker.min.js?url";
import { Worker, Viewer } from '@react-pdf-viewer/core';
import { zoomPlugin } from '@react-pdf-viewer/zoom';
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/zoom/lib/styles/index.css';

// GlobalWorkerOptions.workerSrc = pdfWorkerURL;

// console.log(`Using pdfjs-dist version: ${pdfjsVersion}`);
export default function ReceiptDetail() {
  const { id } = useParams();
  const [rec, setRec] = useState(null);
  const zoom = zoomPlugin();

  useEffect(() => {
    fetch(`/api/receipt/${id}`)
      .then(r => r.json())
      .then(setRec);
  }, [id]);

  if (!rec) return <div>Loading...</div>;

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Receipt Detail</h1>
      <div className="m-4">
        <h2 className='text-red-500 text-2xl'>{rec.error_message}</h2>
      </div>
      <div className="flex h-screen">

      <div className="w-1/2 border-r flex flex-col">
        <div className="p-2 flex gap-2 bg-gray-100">
          <zoom.ZoomOutButton />
          <zoom.ZoomPopover />
          <zoom.ZoomInButton />
        </div>
        <div className="flex-1 overflow-auto">
          <Worker workerUrl={pdfWorkerURL}>
            <Viewer fileUrl={rec.pdf_url} plugins={[zoom]} />
          </Worker>
        </div>
      </div>
      <div className="w-1/2 p-4 overflow-auto">
        <div  className="mb-2"><strong>元のファイル:</strong> {rec.original_pdf_filename}</div>
        <div  className="mb-2"><strong>新しいファイル名:</strong> {rec.generated_receipt_id}</div>
        <div  className="mb-2"><strong>タイムスタンプ:</strong> {rec.processed_timestamp}</div>
        <div  className="mb-2"><strong>相手先:</strong> {rec.vendor_name}</div>
        <div  className="mb-2"><strong>日付:</strong> {rec.date}</div>
        <div  className="mb-2"><strong>金額:</strong> {rec.amount}</div>
        <div  className="mb-2"><strong>消費税:</strong> {rec.tax}</div>
        <div  className="mb-2"><strong>消費税率:</strong> {rec.tax_rate}</div>
        <div  className="mb-2"><strong>摘要:</strong> {(() => {
    try {
      const data = Array.isArray(rec.description) 
        ? rec.description 
        : JSON.parse(rec.description || '[]');
      
      return data.map((item, index) => (
        <div key={index}>
          名前 - {item[0]} - 数量: {item[1]}, 単価: {item[2]}, 合計: {item[3]}
        </div>
      ));
    } catch {
      return <span>No description available</span>;
    }
  })()}</div>
        <div  className="mb-2"><strong>登録番号:</strong> {rec.registration_number}</div>
        <div  className="mb-2"><strong>カテゴリ:</strong> {rec.category}</div>
        <div  className="mb-2"><strong>抽出されたデータ:</strong> {rec.original_extracted_data}</div>
        <div  className="mb-2"><strong>llmによる評価スコア:</strong> {rec.evaluation_score}</div>
        <div  className="mb-2"><strong>llmからのコメント:</strong> {rec.feedback}</div>
      </div>
    </div>
    </div>
    
    
  );
}
