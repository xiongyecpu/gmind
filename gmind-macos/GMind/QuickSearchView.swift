import SwiftUI

struct QuickSearchView: View {
    let onClose: () -> Void
    
    @State private var query = ""
    @State private var results: [SearchResult] = []
    @State private var isSearching = false
    @State private var selectedResult: SearchResult?
    @State private var askMode = false
    @State private var answer = ""
    @State private var answerSources: [Source] = []
    @State private var isAsking = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Search bar
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(.secondary)
                
                TextField("Search your knowledge base...", text: $query)
                    .textFieldStyle(.plain)
                    .onSubmit {
                        if askMode {
                            performAsk()
                        } else {
                            performSearch()
                        }
                    }
                    .onChange(of: query) { _ in
                        if !askMode && query.count >= 2 {
                            performSearch()
                        }
                    }
                
                if isSearching || isAsking {
                    ProgressView()
                        .scaleEffect(0.7)
                }
                
                Button(action: { askMode.toggle() }) {
                    Image(systemName: askMode ? "brain.head.profile" : "sparkles")
                        .foregroundStyle(askMode ? .accentColor : .secondary)
                }
                .buttonStyle(.plain)
                .help(askMode ? "Search mode" : "Ask AI mode")
                
                Button(action: onClose) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding()
            .background(.ultraThinMaterial)
            
            Divider()
            
            // Results
            if askMode && !answer.isEmpty {
                askResultsView
            } else {
                searchResultsView
            }
        }
        .frame(width: 560, height: 480)
    }
    
    private var searchResultsView: some View {
        List(results) { result in
            Button(action: {
                // Open in dashboard
            }) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(result.title)
                            .font(.system(size: 13, weight: .medium))
                        Spacer()
                        Text(String(format: "%.2f", result.similarity))
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    Text(result.preview)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
            .buttonStyle(.plain)
            .padding(.vertical, 2)
        }
        .listStyle(.plain)
        .overlay {
            if results.isEmpty && !query.isEmpty && !isSearching {
                ContentUnavailableView {
                    Label("No results", systemImage: "magnifyingglass")
                } description: {
                    Text('Try a different query or press Enter to ask AI')
                }
            }
        }
    }
    
    private var askResultsView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Answer
                Text(answer)
                    .font(.body)
                    .textSelection(.enabled)
                
                // Sources
                if !answerSources.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Sources")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        
                        ForEach(answerSources) { source in
                            HStack {
                                Text("[[\(source.slug)]]")
                                    .font(.caption)
                                    .foregroundStyle(.accent)
                                Text(source.title)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                Spacer()
                                Text(String(format: "%.2f", source.relevance))
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                    .padding(.top, 8)
                }
            }
            .padding()
        }
    }
    
    private func performSearch() {
        guard query.count >= 2 else { return }
        isSearching = true
        
        GMindAPI.shared.search(query: query, topK: 10) { searchResults in
            DispatchQueue.main.async {
                self.results = searchResults
                self.isSearching = false
            }
        }
    }
    
    private func performAsk() {
        guard !query.isEmpty else { return }
        isAsking = true
        answer = ""
        answerSources = []
        
        GMindAPI.shared.ask(question: query, topK: 8) { result in
            DispatchQueue.main.async {
                isAsking = false
                switch result {
                case .success(let response):
                    answer = response.answer
                    answerSources = response.sources
                case .failure(let error):
                    answer = "❌ Error: \(error.localizedDescription)"
                }
            }
        }
    }
}

#Preview {
    QuickSearchView(onClose: {})
}
