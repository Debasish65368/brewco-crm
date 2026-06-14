import React, { useEffect, useState } from "react";
import axios from "axios";

const API = "https://brewco-crm-backend-7xrd.onrender.com";

const styles = {
  app: { fontFamily: "Arial, sans-serif", backgroundColor: "#f4f6f8", minHeight: "100vh" },
  navbar: { display: "flex", gap: "12px", padding: "15px", backgroundColor: "#1f2937", color: "white", alignItems: "center" },
  navButton: { padding: "10px 16px", border: "none", cursor: "pointer", borderRadius: "6px", backgroundColor: "#374151", color: "white" },
  activeButton: { padding: "10px 16px", border: "none", cursor: "pointer", borderRadius: "6px", backgroundColor: "#2563eb", color: "white" },
  container: { padding: "20px" },
  cardGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: "15px", marginBottom: "20px" },
  card: { backgroundColor: "white", borderRadius: "8px", padding: "20px", boxShadow: "0 2px 8px rgba(0,0,0,0.08)" },
  cardTitle: { color: "#6b7280", fontSize: "14px", marginBottom: "10px" },
  cardValue: { fontSize: "28px", fontWeight: "bold" },
  table: { width: "100%", borderCollapse: "collapse", backgroundColor: "white" },
  th: { textAlign: "left", padding: "12px", borderBottom: "1px solid #ddd", backgroundColor: "#f8fafc" },
  td: { padding: "12px", borderBottom: "1px solid #eee" },
  input: { width: "100%", padding: "10px", marginBottom: "10px", borderRadius: "6px", border: "1px solid #ccc", boxSizing: "border-box" },
  textarea: { width: "100%", minHeight: "120px", padding: "10px", marginBottom: "10px", borderRadius: "6px", border: "1px solid #ccc", boxSizing: "border-box" },
  select: { width: "100%", padding: "10px", marginBottom: "10px", borderRadius: "6px", border: "1px solid #ccc", boxSizing: "border-box" },
  primaryButton: { padding: "10px 16px", border: "none", borderRadius: "6px", cursor: "pointer", backgroundColor: "#2563eb", color: "white", marginRight: "10px" },
  secondaryButton: { padding: "10px 16px", border: "none", borderRadius: "6px", cursor: "pointer", backgroundColor: "#10b981", color: "white", marginRight: "10px" },
  section: { backgroundColor: "white", padding: "20px", borderRadius: "8px", marginBottom: "20px", boxShadow: "0 2px 8px rgba(0,0,0,0.08)" },
  heading: { marginBottom: "15px" },
  pre: { backgroundColor: "#f3f4f6", padding: "10px", borderRadius: "6px", overflowX: "auto" }
};

function Navbar({ page, setPage }) {
  return (
    <div style={styles.navbar}>
      <h2 style={{ marginRight: "20px", margin: "0" }}>☕ BrewCo CRM</h2>
      <button style={page === "dashboard" ? styles.activeButton : styles.navButton} onClick={() => setPage("dashboard")}>Dashboard</button>
      <button style={page === "customers" ? styles.activeButton : styles.navButton} onClick={() => setPage("customers")}>Customers</button>
      <button style={page === "segments" ? styles.activeButton : styles.navButton} onClick={() => setPage("segments")}>Segments</button>
      <button style={page === "campaigns" ? styles.activeButton : styles.navButton} onClick={() => setPage("campaigns")}>Campaigns</button>
    </div>
  );
}

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadDashboard = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/stats`);
      setStats(response.data);
    } catch (error) {
      console.error(error);
      alert("Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadDashboard(); }, []);

  if (loading) return <div style={styles.container}>Loading dashboard...</div>;
  if (!stats) return <div style={styles.container}>No dashboard data available</div>;

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>Dashboard</h2>
      <div style={styles.cardGrid}>
        <div style={styles.card}><div style={styles.cardTitle}>Total Customers</div><div style={styles.cardValue}>{stats.total_customers}</div></div>
        <div style={styles.card}><div style={styles.cardTitle}>Total Orders</div><div style={styles.cardValue}>{stats.total_orders}</div></div>
        <div style={styles.card}><div style={styles.cardTitle}>Revenue</div><div style={styles.cardValue}>₹{Number(stats.total_revenue).toLocaleString()}</div></div>
        <div style={styles.card}><div style={styles.cardTitle}>Campaigns</div><div style={styles.cardValue}>{stats.total_campaigns}</div></div>
        <div style={styles.card}><div style={styles.cardTitle}>Delivery Rate</div><div style={styles.cardValue}>{stats.delivery_rate}%</div></div>
        <div style={styles.card}><div style={styles.cardTitle}>Open Rate</div><div style={styles.cardValue}>{stats.open_rate}%</div></div>
        <div style={styles.card}><div style={styles.cardTitle}>Click Rate</div><div style={styles.cardValue}>{stats.click_rate}%</div></div>
      </div>

      <div style={styles.section}>
        <h3>Communication Metrics</h3>
        <div style={styles.cardGrid}>
          <div style={styles.card}><div style={styles.cardTitle}>Sent</div><div style={styles.cardValue}>{stats.sent}</div></div>
          <div style={styles.card}><div style={styles.cardTitle}>Delivered</div><div style={styles.cardValue}>{stats.delivered}</div></div>
          <div style={styles.card}><div style={styles.cardTitle}>Opened</div><div style={styles.cardValue}>{stats.opened}</div></div>
          <div style={styles.card}><div style={styles.cardTitle}>Clicked</div><div style={styles.cardValue}>{stats.clicked}</div></div>
        </div>
      </div>

      <div style={styles.section}>
        <h3>Recent Campaigns</h3>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>ID</th>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Channel</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Created</th>
            </tr>
          </thead>
          <tbody>
            {(stats.recent_campaigns || []).map((campaign) => (
              <tr key={campaign.id}>
                <td style={styles.td}>{campaign.id}</td>
                <td style={styles.td}>{campaign.name}</td>
                <td style={styles.td}>{campaign.channel}</td>
                <td style={styles.td}>{campaign.status}</td>
                <td style={styles.td}>{new Date(campaign.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Customers() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadCustomers = async () => {
    try {
      const response = await axios.get(`${API}/customers`);
      setCustomers(response.data);
    } catch (error) {
      console.error(error);
      alert("Failed to load customers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadCustomers(); }, []);

  if (loading) return <div style={styles.container}>Loading customers...</div>;

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>Customers ({customers.length})</h2>
      <div style={styles.section}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Email</th>
              <th style={styles.th}>Phone</th>
              <th style={styles.th}>City</th>
              <th style={styles.th}>Orders</th>
              <th style={styles.th}>Total Spent</th>
              <th style={styles.th}>Last Order</th>
            </tr>
          </thead>
          <tbody>
            {customers.map((customer) => (
              <tr key={customer.id}>
                <td style={styles.td}>{customer.name}</td>
                <td style={styles.td}>{customer.email}</td>
                <td style={styles.td}>{customer.phone}</td>
                <td style={styles.td}>{customer.city}</td>
                <td style={styles.td}>{customer.total_orders}</td>
                <td style={styles.td}>₹{Number(customer.total_spent || 0).toLocaleString()}</td>
                <td style={styles.td}>{customer.last_order_date ? new Date(customer.last_order_date).toLocaleDateString() : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {customers.length === 0 && <div style={{ padding: "20px", textAlign: "center" }}>No customers found</div>}
      </div>
    </div>
  );
}

function Segments() {
  const [segments, setSegments] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [naturalLanguage, setNaturalLanguage] = useState("");
  const [filterJson, setFilterJson] = useState("{}");
  const [loading, setLoading] = useState(false);

  const loadSegments = async () => {
    try {
      const response = await axios.get(`${API}/segments`);
      setSegments(response.data);
    } catch (error) {
      console.error(error);
      alert("Failed to load segments");
    }
  };

  useEffect(() => { loadSegments(); }, []);

  const suggestSegment = async () => {
    if (!naturalLanguage.trim()) { alert("Enter a segment description"); return; }
    try {
      setLoading(true);
      const response = await axios.post(`${API}/ai/suggest-segment`, { prompt: naturalLanguage });
      setFilterJson(JSON.stringify(response.data.filter_json, null, 2));
    } catch (error) {
      console.error(error);
      alert("AI segment generation failed");
    } finally {
      setLoading(false);
    }
  };

  const createSegment = async () => {
    try {
      const parsedFilter = JSON.parse(filterJson);
      await axios.post(`${API}/segments`, { name, description, filter_json: parsedFilter });
      setName(""); setDescription(""); setNaturalLanguage(""); setFilterJson("{}");
      await loadSegments();
      alert("Segment created!");
    } catch (error) {
      console.error(error);
      alert("Invalid JSON or failed to create segment");
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>Segments</h2>
      <div style={styles.section}>
        <h3>Create Segment with AI</h3>
        <input style={styles.input} placeholder="Segment Name" value={name} onChange={(e) => setName(e.target.value)} />
        <input style={styles.input} placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
        <textarea style={styles.textarea} placeholder="Describe your audience in plain English e.g. 'Customers who spent more than 500 rupees'" value={naturalLanguage} onChange={(e) => setNaturalLanguage(e.target.value)} />
        <button style={styles.secondaryButton} onClick={suggestSegment} disabled={loading}>{loading ? "Generating..." : "✨ AI Suggest Segment"}</button>
        <h4>Filter JSON (editable)</h4>
        <textarea style={styles.textarea} value={filterJson} onChange={(e) => setFilterJson(e.target.value)} />
        <button style={styles.primaryButton} onClick={createSegment}>Create Segment</button>
      </div>

      <div style={styles.section}>
        <h3>Existing Segments</h3>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>ID</th>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Description</th>
              <th style={styles.th}>Customers</th>
              <th style={styles.th}>Filter</th>
            </tr>
          </thead>
          <tbody>
            {segments.map((segment) => (
              <tr key={segment.id}>
                <td style={styles.td}>{segment.id}</td>
                <td style={styles.td}>{segment.name}</td>
                <td style={styles.td}>{segment.description}</td>
                <td style={styles.td}>{segment.customer_count}</td>
                <td style={styles.td}><pre style={styles.pre}>{JSON.stringify(segment.filter_json, null, 2)}</pre></td>
              </tr>
            ))}
          </tbody>
        </table>
        {segments.length === 0 && <div style={{ padding: "20px", textAlign: "center" }}>No segments found</div>}
      </div>
    </div>
  );
}

function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [segments, setSegments] = useState([]);
  const [name, setName] = useState("");
  const [segmentId, setSegmentId] = useState("");
  const [channel, setChannel] = useState("WhatsApp");
  const [goal, setGoal] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({});

  const loadCampaigns = async () => {
    try { const response = await axios.get(`${API}/campaigns`); setCampaigns(response.data); } catch (error) { console.error(error); }
  };

  const loadSegments = async () => {
    try { const response = await axios.get(`${API}/segments`); setSegments(response.data); } catch (error) { console.error(error); }
  };

  useEffect(() => { loadCampaigns(); loadSegments(); }, []);

  const generateMessage = async () => {
    if (!goal.trim()) { alert("Enter campaign goal"); return; }
    try {
      setLoading(true);
      const response = await axios.post(`${API}/ai/draft-message`, { goal });
      setMessage(response.data.message);
    } catch (error) {
      console.error(error);
      alert("Failed to generate message");
    } finally {
      setLoading(false);
    }
  };

  const createCampaign = async () => {
    if (!name || !segmentId || !message) { alert("Fill all required fields"); return; }
    try {
      await axios.post(`${API}/campaigns`, { name, segment_id: Number(segmentId), channel, message });
      setName(""); setSegmentId(""); setGoal(""); setMessage("");
      await loadCampaigns();
      alert("Campaign created successfully!");
    } catch (error) {
      console.error(error);
      alert("Failed to create campaign");
    }
  };

  const loadStats = async (campaignId) => {
    try {
      const response = await axios.get(`${API}/campaigns/${campaignId}/stats`);
      setStats((prev) => ({ ...prev, [campaignId]: response.data }));
    } catch (error) {
      console.error(error);
      alert("Failed to load stats");
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>Campaigns</h2>
      <div style={styles.section}>
        <h3>Create Campaign</h3>
        <input style={styles.input} placeholder="Campaign Name" value={name} onChange={(e) => setName(e.target.value)} />
        <select style={styles.select} value={segmentId} onChange={(e) => setSegmentId(e.target.value)}>
          <option value="">Select Segment</option>
          {segments.map((segment) => (<option key={segment.id} value={segment.id}>{segment.name}</option>))}
        </select>
        <select style={styles.select} value={channel} onChange={(e) => setChannel(e.target.value)}>
          <option>WhatsApp</option>
          <option>SMS</option>
          <option>Email</option>
        </select>
        <textarea style={styles.textarea} placeholder="Campaign Goal (e.g. win back customers who haven't visited in 30 days)" value={goal} onChange={(e) => setGoal(e.target.value)} />
        <button style={styles.secondaryButton} onClick={generateMessage} disabled={loading}>{loading ? "Generating..." : "✨ AI Draft Message"}</button>
        <textarea style={styles.textarea} placeholder="Campaign Message" value={message} onChange={(e) => setMessage(e.target.value)} />
        <button style={styles.primaryButton} onClick={createCampaign}>🚀 Launch Campaign</button>
      </div>

      <div style={styles.section}>
        <h3>Campaign History</h3>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>ID</th>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Segment</th>
              <th style={styles.th}>Channel</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Created</th>
              <th style={styles.th}>Stats</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((campaign) => (
              <React.Fragment key={campaign.id}>
                <tr>
                  <td style={styles.td}>{campaign.id}</td>
                  <td style={styles.td}>{campaign.name}</td>
                  <td style={styles.td}>{campaign.segment_name || campaign.segment_id}</td>
                  <td style={styles.td}>{campaign.channel}</td>
                  <td style={styles.td}>{campaign.status}</td>
                  <td style={styles.td}>{new Date(campaign.created_at).toLocaleString()}</td>
                  <td style={styles.td}><button style={styles.secondaryButton} onClick={() => loadStats(campaign.id)}>View Stats</button></td>
                </tr>
                {stats[campaign.id] && (
                  <tr>
                    <td colSpan="7" style={{ ...styles.td, backgroundColor: "#f0fdf4" }}>
                      <strong>Sent:</strong> {stats[campaign.id].sent} {" | "}
                      <strong>Delivered:</strong> {stats[campaign.id].delivered} {" | "}
                      <strong>Opened:</strong> {stats[campaign.id].opened} {" | "}
                      <strong>Clicked:</strong> {stats[campaign.id].clicked} {" | "}
                      <strong>Failed:</strong> {stats[campaign.id].failed}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
        {campaigns.length === 0 && <div style={{ padding: "20px", textAlign: "center" }}>No campaigns found</div>}
      </div>
    </div>
  );
}

function App() {
  const [page, setPage] = useState("dashboard");

  const renderPage = () => {
    switch (page) {
      case "dashboard": return <Dashboard />;
      case "customers": return <Customers />;
      case "segments": return <Segments />;
      case "campaigns": return <Campaigns />;
      default: return <Dashboard />;
    }
  };

  return (
    <div style={styles.app}>
      <Navbar page={page} setPage={setPage} />
      {renderPage()}
    </div>
  );
}

export default App;
