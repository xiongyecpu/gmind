import Foundation

/// HTTP client for the GMind Python server.
class GMindAPI {
    static let shared = GMindAPI()
    private let baseURL = "http://127.0.0.1:8765"
    private let session: URLSession
    
    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        session = URLSession(configuration: config)
    }
    
    // MARK: - Add
    
    func addPage(content: String, title: String?, source: String?, completion: @escaping (Result<String, Error>) -> Void) {
        let body: [String: Any] = [
            "content": content,
            "title": title ?? "",
            "source": source ?? "",
            "type": "note",
        ]
        post("/add", body: body) { result in
            switch result {
            case .success(let data):
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let slug = json["slug"] as? String {
                    completion(.success(slug))
                } else {
                    completion(.failure(APIError.invalidResponse))
                }
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
    
    // MARK: - Search
    
    func search(query: String, topK: Int = 8, completion: @escaping ([SearchResult]) -> Void) {
        guard let url = URL(string: "\(baseURL)/search?q=\(encode(query))&k=\(topK)") else {
            completion([])
            return
        }
        
        session.dataTask(with: url) { data, _, _ in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let results = json["results"] as? [[String: Any]] else {
                completion([])
                return
            }
            
            let mapped = results.compactMap { dict -> SearchResult? in
                guard let slug = dict["slug"] as? String,
                      let title = dict["title"] as? String else { return nil }
                return SearchResult(
                    slug: slug,
                    title: title,
                    preview: dict["preview"] as? String ?? "",
                    similarity: dict["similarity"] as? Double ?? 0
                )
            }
            completion(mapped)
        }.resume()
    }
    
    // MARK: - Ask
    
    func ask(question: String, topK: Int = 8, completion: @escaping (Result<AskResponse, Error>) -> Void) {
        let body: [String: Any] = [
            "question": question,
            "top_k": topK,
        ]
        post("/ask", body: body) { result in
            switch result {
            case .success(let data):
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let answer = json["answer"] as? String {
                    let sources = (json["sources"] as? [[String: Any]] ?? []).compactMap { dict -> Source? in
                        guard let slug = dict["slug"] as? String,
                              let title = dict["title"] as? String else { return nil }
                        return Source(slug: slug, title: title, relevance: dict["relevance"] as? Double ?? 0)
                    }
                    completion(.success(AskResponse(answer: answer, sources: sources)))
                } else {
                    completion(.failure(APIError.invalidResponse))
                }
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
    
    // MARK: - Stats
    
    func fetchStats(completion: @escaping (Stats?) -> Void) {
        // For now, query the stats via a simple page count
        // We can extend server.py with a /stats endpoint later
        guard let url = URL(string: "\(baseURL)/search?q=*&k=1") else {
            completion(nil)
            return
        }
        session.dataTask(with: url) { _, response, _ in
            let online = (response as? HTTPURLResponse)?.statusCode == 200
            completion(online ? Stats(pageCount: 0) : nil)
        }.resume()
    }
    
    func fetchRecent(limit: Int = 5, completion: @escaping ([Page]) -> Void) {
        // Placeholder — would need a /recent endpoint on server
        // For now return empty, will be wired up later
        completion([])
    }
    
    // MARK: - Private
    
    private func post(_ path: String, body: [String: Any], completion: @escaping (Result<Data, Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            completion(.failure(APIError.invalidURL))
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        session.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data else {
                completion(.failure(APIError.noData))
                return
            }
            completion(.success(data))
        }.resume()
    }
    
    private func encode(_ string: String) -> String {
        string.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? string
    }
}

// MARK: - Models

struct SearchResult: Identifiable {
    let id = UUID()
    let slug: String
    let title: String
    let preview: String
    let similarity: Double
}

struct Source: Identifiable {
    let id = UUID()
    let slug: String
    let title: String
    let relevance: Double
}

struct AskResponse {
    let answer: String
    let sources: [Source]
}

struct Stats {
    let pageCount: Int
}

struct Page: Identifiable {
    let id = UUID()
    let slug: String
    let title: String
}

enum APIError: Error {
    case invalidURL
    case invalidResponse
    case noData
}
