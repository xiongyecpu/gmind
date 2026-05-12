import SwiftUI
import WebKit

struct DashboardView: View {
    @State private var selectedTab = 0
    
    var body: some View {
        TabView(selection: $selectedTab) {
            StatsTabView()
                .tabItem {
                    Label("Stats", systemImage: "chart.bar")
                }
                .tag(0)
            
            GraphTabView()
                .tabItem {
                    Label("Graph", systemImage: "network")
                }
                .tag(1)
            
            RecentTabView()
                .tabItem {
                    Label("Recent", systemImage: "clock")
                }
                .tag(2)
        }
        .frame(minWidth: 800, minHeight: 600)
    }
}

// MARK: - Stats Tab

struct StatsTabView: View {
    @State private var stats: ServerStats?
    @State private var isLoading = true
    
    var body: some View {
        VStack {
            if isLoading {
                ProgressView("Loading stats...")
            } else if let stats = stats {
                StatsGrid(stats: stats)
            } else {
                ContentUnavailableView {
                    Label("Server Offline", systemImage: "wifi.slash")
                } description: {
                    Text("Make sure gmind serve is running")
                }
            }
        }
        .padding()
        .onAppear { loadStats() }
    }
    
    private func loadStats() {
        // TODO: Wire up to /stats endpoint
        isLoading = false
    }
}

struct StatsGrid: View {
    let stats: ServerStats
    
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 180))], spacing: 16) {
            StatCard(title: "Pages", value: "\(stats.pageCount)", icon: "doc.text")
            StatCard(title: "Edges", value: "\(stats.edgeCount)", icon: "link")
            StatCard(title: "Entities", value: "\(stats.entityCount)", icon: "tag")
            StatCard(title: "Drafts", value: "\(stats.draftCount)", icon: "pencil")
        }
    }
}

struct StatCard: View {
    let title: String
    let value: String
    let icon: String
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(.accent)
            Text(value)
                .font(.system(size: 32, weight: .bold))
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 120)
        .background(.ultraThinMaterial)
        .cornerRadius(12)
    }
}

struct ServerStats {
    let pageCount: Int
    let edgeCount: Int
    let entityCount: Int
    let draftCount: Int
}

// MARK: - Graph Tab

struct GraphTabView: View {
    var body: some View {
        WebView(url: URL(string: "http://127.0.0.1:8765/graph/view")!)
            .overlay {
                // Fallback if no web graph view available yet
                ContentUnavailableView {
                    Label("Graph View", systemImage: "network")
                } description: {
                    Text("Knowledge graph visualization coming soon")
                }
            }
    }
}

// MARK: - Recent Tab

struct RecentTabView: View {
    @State private var pages: [Page] = []
    
    var body: some View {
        List(pages) { page in
            HStack {
                Text(page.title)
                Spacer()
                Text("[[\(page.slug)]]")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .onAppear {
            GMindAPI.shared.fetchRecent(limit: 50) { fetched in
                pages = fetched
            }
        }
    }
}

// MARK: - WebView

struct WebView: NSViewRepresentable {
    let url: URL
    
    func makeNSView(context: Context) -> WKWebView {
        WKWebView()
    }
    
    func updateNSView(_ nsView: WKWebView, context: Context) {
        let request = URLRequest(url: url)
        nsView.load(request)
    }
}

#Preview {
    DashboardView()
}
