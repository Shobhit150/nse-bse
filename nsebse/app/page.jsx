"use client"
import { useEffect, useRef, useState } from "react"

export default function Home() {
  const [data, setData] = useState([])
  const [meta, setMeta] = useState({})
  const [status, setStatus] = useState("disconnected")
  const [error, setError] = useState(null)
  const [messageCount, setMessageCount] = useState(0)
  const [expanded, setExpanded] = useState(false)

  const socketRef = useRef(null)
  const prevHashRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  const formatTime = (ts) => {
    if (!ts) return "—"
    return new Date(ts * 1000).toLocaleString()
  }

  const connect = () => {
    setStatus("connecting")
    setError(null)

    const ws = new WebSocket("ws://127.0.0.1:8000/ws/nse")
    socketRef.current = ws

    ws.onopen = () => setStatus("connected")

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (!msg?.data) return

        const hash = JSON.stringify(msg.data)
        if (hash === prevHashRef.current) return
        prevHashRef.current = hash

        setData(msg.data)
        setMeta(msg.meta || {})
        setMessageCount((c) => c + 1)
      } catch (err) {
        setError(err.message)
      }
    }

    ws.onerror = () => {
      setStatus("error")
      setError("WebSocket error")
    }

    ws.onclose = () => {
      setStatus("disconnected")
      reconnectTimeoutRef.current = setTimeout(connect, 3000)
    }
  }

  useEffect(() => {
    connect()
    return () => {
      socketRef.current?.close()
      clearTimeout(reconnectTimeoutRef.current)
    }
  }, [])

  const statusBadge = {
    connected: "bg-green-600",
    connecting: "bg-yellow-500",
    error: "bg-red-600",
    disconnected: "bg-gray-500",
  }[status]

  const issueSize = meta.issue_size || 0

  const previewRows =
    data.length > 6
      ? [...data.slice(0, 3), ...data.slice(-3)]
      : data

  return (
    <div className="max-w-6xl mx-auto p-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">OFS Order Book</h1>
        <span className={`text-xs px-3 py-1 rounded-full text-white ${statusBadge}`}>
          {status.toUpperCase()}
        </span>
      </div>

      {/* Summary Table */}
     
        <div className="grid grid-cols-3 border text-sm mb-4">

          <GridItem
            label="Subscription"
            value={meta.subscription_pct ? `${meta.subscription_pct.toFixed(2)}%` : "—"}
          />
          <GridItem
            label="Remaining Qty"
            value={meta.remaining_qty?.toLocaleString() ?? "—"}
          />

          <GridItem label="Cutoff Price" value={meta.cutoff_price ?? "—"} />
          <GridItem label="Top Price" value={meta.top_price ?? "—"} />

          <GridItem
            label="Issue Size"
            value={meta.issue_size?.toLocaleString() ?? "—"}
          />
          <GridItem label="NSE Time" value={formatTime(meta.nse_last_updated_ts)} />
          <GridItem label="BSE Time" value={formatTime(meta.bse_last_updated_ts)} />
        </div>


      {/* Preview Table (Top + Bottom 3) */}
      {previewRows.length > 0 && (
        <div className="mb-4 overflow-hidden rounded-lg border bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">Price</th>
                <th className="px-3 py-2 text-right">Qty</th>
                <th className="px-3 py-2 text-right">Cumulative</th>

              </tr>
            </thead>
            <tbody>
              {previewRows.map((row, i) => (
                <tr key={`${row.price}-${i}`} className="border-t">
                  <td className="px-3 py-2">{row.price}</td>
                  <td className="px-3 py-2 text-right">
                    {row.qty.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {row.cumulative_qty.toLocaleString()}
                  </td>

                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Toggle */}
      {data.length > 0 && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mb-3 flex items-center gap-2 rounded border px-3 py-1 text-sm hover:bg-slate-100"
        >
          <span className="font-bold">{expanded ? "−" : "+"}</span>
          {expanded ? "Hide Full Order Book" : "Show Full Order Book"}
        </button>
      )}

      {/* Full Table */}
      {expanded && (
        <div className="overflow-hidden rounded-lg border bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">Price</th>
                <th className="px-3 py-2 text-right">Qty</th>
                <th className="px-3 py-2 text-right">Cumulative</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr key={`${row.price}-${i}`} className="border-t">
                  <td className="px-3 py-2">{row.price}</td>
                  <td className="px-3 py-2 text-right">
                    {row.qty.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {row.cumulative_qty.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 rounded border border-red-300 bg-red-50 px-4 py-2 text-red-700">
          {error}
        </div>
      )}
    </div>
  )
}

/* ---------- Helpers ---------- */

function GridItem({ label, value }) {
  return (
    <div className="flex flex-row justify-between border px-4 py-2">
      <span className="text-xs text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  )
}
