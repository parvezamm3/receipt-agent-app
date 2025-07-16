import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

export default function App() {
  const [data, setData] = useState({ successful: [], failed: [] });
  useEffect(() => {
    // Fetch data on initial load
    fetchReceipts();

    // Set up EventSource for subsequent updates
    const es = new EventSource('/api/stream');
    // whenever the server sends "update", re‑fetch table data
    es.addEventListener('update', () => fetchReceipts());
    return () => es.close();
  }, []);

  const [search, setSearch] = useState("");

  const filtered = data.successful.filter(r => {
    const term = search.toLowerCase();
    return (
      r.id.toLowerCase().includes(term) ||
      r.date.toLowerCase().includes(term) ||
      r.amount.toString().toLowerCase().includes(term) ||
      (r.vendor_name || "").toLowerCase().includes(term)||
      (r.category || "").toLowerCase().includes(term)
    );
  });
 

  const fetchReceipts = () => {
    fetch('/api/receipts')
      .then(r => r.json())
      .then(receipts => {
        setData({
          successful: receipts.successful,
          failed: receipts.failed
        });
      });
  };
//  console.log(data.successful);
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Receipt Dashboard</h1>
      <div className="grid grid-cols-2 gap-8">
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Successful</h2>
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="px-3 py-1 border border-gray-300 rounded-md focus:outline-none focus:ring"
            />
          </div>
          <table className="table-fixed w-full border-collapse border border-gray-300">
            <thead className="bg-gray-100">
              <tr>
                <th className="px-2 py-1 text-left border border-gray-300">ID</th>
                <th className="px-2 py-1 text-left border border-gray-300">日付</th>
                <th className="px-2 py-1 text-left border border-gray-300">金額</th>
                <th className="w-90 px-2 py-1 text-left border border-gray-300">相手先</th>
                <th className="px-2 py-1 text-left border border-gray-300">カテゴリ</th>
                <th className="px-2 py-1 text-left border border-gray-300">評価スコア</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr
                  key={r.id}
                  className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}
                >
                  <td className="px-2 py-1 border border-gray-300 wrap-break-word">
                    <Link className="text-blue-600" to={`/receipt/${r.id}`}>
                      {r.id}
                    </Link>
                  </td>
                  <td className="px-2 py-1 border border-gray-300 wrap-break-word">
                    {r.date}
                  </td>
                  <td className="px-2 py-1 border border-gray-300 wrap-break-word">
                    {r.amount}
                  </td>
                  <td className="px-2 py-1 border border-gray-300 wrap-break-word">
                    {r.vendor_name}
                  </td>
                  <td className="px-2 py-1 border border-gray-300 wrap-break-word">
                    {r.category}
                  </td>
                  <td className="px-2 py-1 border border-gray-300 wrap-break-word">
                    {r.score}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h2 className="text-xl font-semibold mb-2">Failed</h2>
          <table className="min-w-full border bg-red-50">
            <thead><tr>
              <th className="px-2 py-1 text-left border border-gray-300">ID</th>
              <th className="px-2 py-1 text-left border border-gray-300">元のファイル</th>
              <th className="px-2 py-1 text-left border border-gray-300">エラーメッセージ</th>
              <th className="px-2 py-1 text-left border border-gray-300">評価スコア</th>
            </tr></thead>
            <tbody>
              {data.failed.map(r => (
                <tr key={r.id}>
                  <td className="px-2 py-1 border border-gray-300 wrap-break-word">
                    <Link className="text-blue-600" to={`/receipt/${r.id}`}>{r.id}</Link>
                  </td>
                  <td className="px-2 py-1 border border-gray-300">
                    <div className="max-w-60 overflow-x-auto whitespace-nowrap">
                      {r.filename}
                    </div>
                  </td>
                  <td className="px-2 py-1 border border-gray-300 wrap-break-word">{r.error}</td>
                  <td className="px-2 py-1 border border-gray-300 wrap-break-word">{r.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
