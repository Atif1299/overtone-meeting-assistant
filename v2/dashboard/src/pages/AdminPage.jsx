import { useEffect, useState } from "react";
import { createCustomer, listCustomers } from "../utils/api";

export default function AdminPage({ onLogout, onAuthExpired }) {
  const [customers, setCustomers] = useState([]);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState("");

  async function loadCustomers() {
    try {
      setLoading(true);
      const data = await listCustomers();
      setCustomers(data);
    } catch (err) {
      if (err?.status === 401) {
        setMessage("Session expired. Please login again.");
        onAuthExpired?.();
        return;
      }
      setMessage(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e) {
    e.preventDefault();

    if (!name.trim()) return;

    try {
      setCreating(true);
      const res = await createCustomer(name);

      setMessage(`Created: ${res.customer_name} | API KEY: ${res.api_key}`);
      setName("");
      await loadCustomers();
    } catch (err) {
      if (err?.status === 401) {
        setMessage("Session expired. Please login again.");
        onAuthExpired?.();
        return;
      }
      setMessage(err.message);
    } finally {
      setCreating(false);
    }
  }

  function copyKey(key) {
    navigator.clipboard.writeText(key);
    setMessage("API Key copied successfully");
  }

  useEffect(() => {
    loadCustomers();
  }, []);

  return (
    <>
      <style>{`
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
          font-family: Inter, sans-serif;
        }

        body {
          background: linear-gradient(135deg, #0f172a, #1e293b);
        }

        .admin-page {
          min-height: 100vh;
          padding: 40px;
          color: white;
        }

        .title {
          font-size: 38px;
          font-weight: 700;
          margin-bottom: 30px;
          color: #f8fafc;
        }

        .card {
          background: rgba(255,255,255,0.05);
          backdrop-filter: blur(14px);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 18px;
          padding: 25px;
          box-shadow: 0 10px 30px rgba(0,0,0,0.25);
          margin-bottom: 25px;
        }
        .card-heading {
          margin-bottom: 20px !important;
        }

        .create-box {
          display: flex;
          gap: 14px;
        }

        .create-box input {
          flex: 1;
          padding: 15px;
          border: none;
          border-radius: 12px;
          background: rgba(255,255,255,0.08);
          color: white;
          font-size: 15px;
          outline: none;
        }

        .create-box input::placeholder {
          color: #cbd5e1;
        }

        button {
          border: none;
          border-radius: 12px;
          padding: 14px 20px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: 0.25s ease;
        }

        .primary-btn {
          background: linear-gradient(135deg, #22c55e, #16a34a);
          color: white;
        }

        .primary-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 10px 20px rgba(34,197,94,.25);
        }

        .refresh-btn {
          background: rgba(255,255,255,0.08);
          color: white;
        }

        .refresh-btn:hover {
          background: rgba(255,255,255,0.14);
        }

        .copy-btn {
          background: #0ea5e9;
          color: white;
          padding: 8px 12px;
          border-radius: 8px;
          font-size: 12px;
        }

        .copy-btn:hover {
          background: #0284c7;
        }

        .message {
          margin-top: 18px;
          background: rgba(34,197,94,0.12);
          border: 1px solid rgba(34,197,94,0.3);
          padding: 14px;
          border-radius: 12px;
          color: #bbf7d0;
        }

        .header-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 22px;
        }

        .header-row h2 {
          font-size: 24px;
        }

        table {
          width: 100%;
          border-collapse: collapse;
          overflow: hidden;
          border-radius: 12px;
        }

        thead {
          background: rgba(255,255,255,0.05);
        }

        th {
          text-align: left;
          padding: 16px;
          color: #cbd5e1;
          font-size: 14px;
          font-weight: 600;
        }

        td {
          padding: 16px;
          border-top: 1px solid rgba(255,255,255,0.06);
          color: #f8fafc;
        }

        tbody tr:hover {
          background: rgba(255,255,255,0.04);
        }

        .key {
          color: #38bdf8;
          margin-right: 10px;
          font-weight: 500;
        }

        .status {
          padding: 6px 10px;
          border-radius: 30px;
          font-size: 12px;
          font-weight: 600;
          display: inline-block;
        }

        .active {
          background: rgba(34,197,94,0.18);
          color: #86efac;
        }

        .disabled {
          background: rgba(239,68,68,0.15);
          color: #fca5a5;
        }

        .logout-btn {
          background: rgba(248, 113, 113, 0.18);
          color: #fecaca;
        }

        .logout-btn:hover {
          background: rgba(248, 113, 113, 0.28);
        }

        .loading {
          text-align: center;
          padding: 30px;
          color: #cbd5e1;
        }

        @media (max-width: 900px) {
          .create-box,
          .header-row {
            flex-direction: column;
            align-items: stretch;
          }

          table {
            display: block;
            overflow-x: auto;
            white-space: nowrap;
          }
        }
      `}</style>

      <div className="admin-page">
        <div className="header-row">
          <h1 className="title">Admin Customer Panel</h1>
          <button onClick={() => onLogout?.()} className="logout-btn">
            Logout
          </button>
        </div>

        <div className="card">
            <div className="card-heading">
            <h2>Create Customer</h2>
            </div>
          <form onSubmit={handleCreate} className="create-box">
            <input
              type="text"
              placeholder="Enter customer name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
            />

            <button
              type="submit"
              className="primary-btn"
              disabled={creating}
            >
              {creating ? "Creating..." : "Create Customer"}
            </button>
          </form>

          {message && <div className="message">{message}</div>}
        </div>

        <div className="card">
          <div className="header-row">
            <h2>Customers List</h2>
            <button
              onClick={loadCustomers}
              className="refresh-btn"
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="loading">Loading customers...</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Customer ID</th>
                  <th>API Key</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>

              <tbody>
                {customers.map((c) => (
                  <tr key={c.customer_id}>
                    <td>{c.customer_name}</td>
                    <td>{c.customer_id}</td>

                    <td>
                      <span className="key">
                        {c.api_key.slice(0, 12)}...
                      </span>

                      <button
                        className="copy-btn"
                        onClick={() => copyKey(c.api_key)}
                      >
                        Copy
                      </button>
                    </td>

                    <td>
                      <span
                        className={`status ${
                          c.is_active
                            ? "active"
                            : "disabled"
                        }`}
                      >
                        {c.is_active
                          ? "Active"
                          : "Disabled"}
                      </span>
                    </td>

                    <td>{c.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}