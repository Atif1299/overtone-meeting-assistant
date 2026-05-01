import { useState } from "react";
import { setAdminSession, verifyAdminApiKey } from "../utils/api";

export default function Testform({ onAuthSuccess }) {
  const [apiKey, setApiKey] = useState("");
  const [response, setResponse] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleVerify(e) {
    e.preventDefault();

    setError("");
    setResponse(null);

    if (!apiKey.trim()) {
      setError("admin_api_key is required");
      return;
    }

    try {
      setIsSubmitting(true);
      const result = await verifyAdminApiKey(apiKey.trim());
      setAdminSession(apiKey.trim());
      setResponse(result);
      onAuthSuccess?.();
    } catch (err) {
      setError(err.message || "Invalid admin_api_key");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <style>{`
        *{
          margin:0;
          padding:0;
          box-sizing:border-box;
          font-family:Inter,sans-serif;
        }

        body{
          background:#0f172a;
        }

        .page{
          min-height:100vh;
          padding:40px;
          background:linear-gradient(135deg,#0f172a,#1e293b);
          color:white;
        }

        .wrap{
          max-width:900px;
          margin:auto;
        }

        .title{
          font-size:36px;
          font-weight:700;
          margin-bottom:10px;
        }

        .sub{
          color:#94a3b8;
          margin-bottom:30px;
        }

        .card{
          background:rgba(255,255,255,.05);
          border:1px solid rgba(255,255,255,.08);
          border-radius:18px;
          padding:28px;
          backdrop-filter:blur(12px);
        }

        .top{
          display:flex;
          align-items:center;
          gap:12px;
          margin-bottom:18px;
          flex-wrap:wrap;
        }

        .method{
          background:#22c55e;
          padding:6px 10px;
          border-radius:8px;
          font-size:12px;
          font-weight:700;
        }

        .url{
          font-size:22px;
          font-weight:600;
        }

        .desc{
          color:#cbd5e1;
          line-height:1.6;
          margin-bottom:28px;
        }

        .label{
          display:block;
          margin-bottom:10px;
          color:#94a3b8;
          font-size:14px;
        }

        .input{
          width:100%;
          padding:15px;
          border:none;
          border-radius:12px;
          background:rgba(255,255,255,.08);
          color:white;
          outline:none;
          font-size:15px;
        }

        .btns{
          display:flex;
          gap:12px;
          margin-top:18px;
          flex-wrap:wrap;
        }

        button{
          border:none;
          padding:14px 18px;
          border-radius:12px;
          font-weight:600;
          cursor:pointer;
        }

        .primary{
          background:#22c55e;
          color:white;
        }

        .secondary{
          background:#334155;
          color:white;
        }

        .box{
          margin-top:22px;
          background:#020617;
          padding:18px;
          border-radius:14px;
          border:1px solid rgba(255,255,255,.08);
        }

        .success{
          color:#86efac;
          margin-bottom:10px;
          font-weight:600;
        }

        .err{
          color:#fca5a5;
          margin-top:18px;
          background:rgba(239,68,68,.12);
          padding:14px;
          border-radius:12px;
        }

        pre{
          white-space:pre-wrap;
          color:#93c5fd;
          font-size:14px;
        }

        .hint{
          margin-top:20px;
          color:#94a3b8;
          font-size:14px;
        }
      `}</style>

      <div className="page">
        <div className="wrap">
          <h1 className="title">Admin API Sample Test</h1>
          <p className="sub">
            Enter your admin API key to authenticate and open the admin page.
          </p>

          <div className="card">
            <div className="top">
              <span className="method">POST</span>
              <span className="url">/auth/admin</span>
            </div>

            <p className="desc">
              Verify provided admin_api_key against configured ADMIN_API_KEY.
            </p>

            <form onSubmit={handleVerify}>
              <label className="label">Admin API Key</label>

              <input
                className="input"
                type="password"
                placeholder="Enter admin key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />

              <div className="btns">
                <button className="primary" type="submit">
                  {isSubmitting ? "Verifying..." : "Verify Admin"}
                </button>

                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setApiKey("");
                    setResponse(null);
                    setError("");
                  }}
                >
                  Reset
                </button>
              </div>
            </form>

            {response && (
              <div className="box">
                <div className="success">
                  Successful Response (200)
                </div>
                <pre>{JSON.stringify(response, null, 2)}</pre>
              </div>
            )}

            {error && (
              <div className="err">{error}</div>
            )}

            <div className="hint">
              Use the same key configured as <b>ADMIN_API_KEY</b> in backend env.
            </div>

            <div className="box">
              <pre>{`Request Body:
{
  "admin_api_key": "<your-admin-api-key>"
}`}</pre>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}