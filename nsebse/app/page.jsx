"use client"
import { useEffect, useRef, useState } from 'react'

export default function Home() {
  const [data, setData] = useState([])
  const [status, setStatus] = useState('disconnected')
  const [error, setError] = useState(null)
  const [messageCount, setMessageCount] = useState(0)

  const socketRef = useRef(null)
  const prevHashRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  const connect = () => {
    console.log('🔌 Attempting to connect to WebSocket...')
    setStatus('connecting')
    setError(null)

    const ws = new WebSocket('ws://127.0.0.1:8000/ws/nse')
    socketRef.current = ws

    ws.onopen = () => {
      console.log('✅ WebSocket CONNECTED')
      setStatus('connected')
      setError(null)
    }

    ws.onmessage = (event) => {
      console.log('📨 Received message:', event.data.substring(0, 100) + '...')
      
      try {
        const newData = JSON.parse(event.data)
        
        // Ignore ping messages
        if (newData.type === 'ping') {
          console.log('🏓 Ping received')
          return
        }

        setMessageCount(prev => prev + 1)
        console.log(`📊 Message #${messageCount + 1}, Items: ${newData.length}`)

        const hash = JSON.stringify(newData)
        if (hash !== prevHashRef.current) {
          console.log('✅ Data changed, updating state')
          prevHashRef.current = hash
          setData(newData)
        } else {
          console.log('⏭️  Data unchanged')
        }
      } catch (err) {
        console.error('❌ Failed to parse message:', err)
        setError(`Parse error: ${err.message}`)
      }
    }

    ws.onerror = (err) => {
      console.error('❌ WebSocket ERROR:', err)
      setError('WebSocket error occurred')
      setStatus('error')
    }

    ws.onclose = (event) => {
      console.log('❌ WebSocket CLOSED:', {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean
      })
      setStatus('disconnected')
      setError(`Connection closed (code: ${event.code})`)
      
      // Auto-reconnect after 3 seconds
      console.log('🔄 Reconnecting in 3 seconds...')
      reconnectTimeoutRef.current = setTimeout(connect, 3000)
    }
  }

  useEffect(() => {
    connect()

    return () => {
      console.log('🧹 Cleaning up...')
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (socketRef.current) {
        socketRef.current.close()
      }
    }
  }, [])

  return (
    <div style={{ padding: '20px', fontFamily: 'monospace' }}>
      <h1>OFS Merged Data</h1>
      
      {/* Status Banner */}
      <div style={{
        padding: '10px',
        marginBottom: '20px',
        borderRadius: '5px',
        backgroundColor: 
          status === 'connected' ? '#d4edda' :
          status === 'connecting' ? '#fff3cd' :
          status === 'error' ? '#f8d7da' : '#e2e3e5',
        border: '1px solid',
        borderColor:
          status === 'connected' ? '#c3e6cb' :
          status === 'connecting' ? '#ffeeba' :
          status === 'error' ? '#f5c6cb' : '#d6d8db'
      }}>
        <strong>Status:</strong> {status.toUpperCase()} | 
        <strong> Messages:</strong> {messageCount} | 
        <strong> Items:</strong> {data.length}
        {error && <div style={{ color: 'red', marginTop: '5px' }}>Error: {error}</div>}
      </div>

      {status !== 'connected' && (
        <div style={{ padding: '20px', backgroundColor: '#fff3cd', marginBottom: '20px' }}>
          <h3>⚠️ Not Connected</h3>
          <p>Make sure the backend is running on <code>http://127.0.0.1:8000</code></p>
          <p>Test it by visiting: <a href="http://127.0.0.1:8000/health" target="_blank">http://127.0.0.1:8000/health</a></p>
          <button onClick={connect} style={{ padding: '10px 20px', cursor: 'pointer' }}>
            Retry Connection
          </button>
        </div>
      )}

      {data.length === 0 ? (
        <div style={{ padding: '20px', backgroundColor: '#e2e3e5' }}>
          {status === 'connected' ? 'Connected. Waiting for data...' : 'No data yet'}
        </div>
      ) : (
        <table border="1" cellPadding="6" style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr style={{ backgroundColor: '#f0f0f0' }}>
              <th>Price</th>
              <th>Qty</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.price}>
                <td>{row.price}</td>
                <td>{row.qty}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}