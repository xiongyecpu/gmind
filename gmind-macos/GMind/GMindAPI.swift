import Foundation
import os.log

let apiLog = OSLog(subsystem: "com.gmind.macos", category: "API")

/// HTTP client for the GMind Python server.
class GMindAPI {
    static let shared = GMindAPI()
    private let baseURL = URL(string: "http://127.0.0.1:8765")!
    private let session: URLSession

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        session = URLSession(configuration: config)
        os_log("API init, baseURL=%{public}@", log: apiLog, type: .debug, baseURL.absoluteString)
    }

    // MARK: - Add

    func addPage(content: String, title: String?, source: String?, completion: @escaping (Result<String, Error>) -> Void) {
        let body: [String: Any] = [
            "content": content,
            "title": title ?? "",
            "source": source ?? "",
            "type": "note",
        ]
        os_log("addPage called", log: apiLog, type: .debug)
        post("/add", body: body) { result in
            switch result {
            case .success(let data):
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let slug = json["slug"] as? String {
                    os_log("addPage success slug=%{public}@", log: apiLog, type: .debug, slug)
                    completion(.success(slug))
                } else {
                    os_log("addPage invalidResponse", log: apiLog, type: .error)
                    completion(.failure(APIError.invalidResponse))
                }
            case .failure(let error):
                os_log("addPage error=%{public}@", log: apiLog, type: .error, error.localizedDescription)
                completion(.failure(error))
            }
        }
    }

    // MARK: - Search

    func search(query: String, topK: Int = 8, completion: @escaping ([SearchResult]) -> Void) {
        var components = URLComponents(url: baseURL.appendingPathComponent("search"), resolvingAgainstBaseURL: true)
        components?.queryItems = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "k", value: String(topK)),
        ]
        guard let url = components?.url else {
            os_log("search URL nil! components=%{public}@", log: apiLog, type: .fault, components?.description ?? "nil")
            completion([])
            return
        }
        os_log("search url=%{public}@", log: apiLog, type: .debug, url.absoluteString)

        session.dataTask(with: url) { data, response, error in
            if let error = error {
                os_log("search network error=%{public}@", log: apiLog, type: .error, error.localizedDescription)
                completion([])
                return
            }
            guard let data = data else {
                os_log("search no data, response=%{public}@", log: apiLog, type: .error, String(describing: response))
                completion([])
                return
            }
            guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                os_log("search json parse fail, raw=%{public}@", log: apiLog, type: .error, String(data: data, encoding: .utf8) ?? "<binary>")
                completion([])
                return
            }
            guard let results = json["results"] as? [[String: Any]] else {
                os_log("search no 'results' key, json=%{public}@", log: apiLog, type: .error, String(describing: json.keys))
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
            os_log("search success count=%d", log: apiLog, type: .debug, mapped.count)
            completion(mapped)
        }.resume()
    }

    // MARK: - Ask

    func ask(question: String, topK: Int = 8, completion: @escaping (Result<AskResponse, Error>) -> Void) {
        os_log("ask called question=%{public}@", log: apiLog, type: .debug, question)
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
                    os_log("ask success", log: apiLog, type: .debug)
                    completion(.success(AskResponse(answer: answer, sources: sources)))
                } else {
                    os_log("ask invalidResponse", log: apiLog, type: .error)
                    completion(.failure(APIError.invalidResponse))
                }
            case .failure(let error):
                os_log("ask error=%{public}@", log: apiLog, type: .error, error.localizedDescription)
                completion(.failure(error))
            }
        }
    }

    // MARK: - Stats

    func fetchStats(completion: @escaping (Stats?) -> Void) {
        let url = baseURL.appendingPathComponent("stats")
        os_log("fetchStats url=%{public}@", log: apiLog, type: .debug, url.absoluteString)
        session.dataTask(with: url) { data, response, error in
            if let error = error {
                os_log("fetchStats network error=%{public}@", log: apiLog, type: .error, error.localizedDescription)
                completion(nil)
                return
            }
            guard let data = data else {
                os_log("fetchStats no data, response=%{public}@", log: apiLog, type: .error, String(describing: response))
                completion(nil)
                return
            }
            guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                os_log("fetchStats json parse fail, raw=%{public}@", log: apiLog, type: .error, String(data: data, encoding: .utf8) ?? "<binary>")
                completion(nil)
                return
            }
            os_log("fetchStats json=%{public}@", log: apiLog, type: .debug, String(describing: json))
            guard let pageCount = json["pages"] as? Int else {
                os_log("fetchStats no 'pages' key", log: apiLog, type: .error)
                completion(nil)
                return
            }
            os_log("fetchStats success pages=%d", log: apiLog, type: .debug, pageCount)
            completion(Stats(pageCount: pageCount))
        }.resume()
    }

    func fetchRecent(limit: Int = 5, completion: @escaping ([Page]) -> Void) {
        var components = URLComponents(url: baseURL.appendingPathComponent("recent"), resolvingAgainstBaseURL: true)
        components?.queryItems = [URLQueryItem(name: "limit", value: String(limit))]
        guard let url = components?.url else {
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
            let pages = results.compactMap { dict -> Page? in
                guard let slug = dict["slug"] as? String,
                      let title = dict["title"] as? String else { return nil }
                return Page(slug: slug, title: title)
            }
            completion(pages)
        }.resume()
    }

        // MARK: - Taotie

    func taotieScan(completion: @escaping (Result<TaotieScanResult, Error>) -> Void) {
        let url = baseURL.appendingPathComponent("taotie/scan")
        session.dataTask(with: url) { data, _, _ in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let status = json["status"] as? String, status == "ok" else {
                completion(.failure(APIError.invalidResponse))
                return
            }
            let files = (json["files"] as? [[String: Any]] ?? []).compactMap { dict -> TaotieFile? in
                guard let path = dict["path"] as? String else { return nil }
                return TaotieFile(
                    path: path,
                    size: dict["size"] as? Int ?? 0,
                    ext: dict["ext"] as? String ?? "",
                    shouldIngest: dict["should_ingest"] as? Bool ?? true,
                    reason: dict["reason"] as? String ?? "",
                    privacyLevel: dict["privacy_level"] as? String ?? "safe",
                    containsPasswords: dict["contains_passwords"] as? Bool ?? false,
                    containsPII: dict["contains_pii"] as? Bool ?? false,
                    isKnowledge: dict["is_knowledge"] as? Bool ?? true
                )
            }
            let folders = (json["folders"] as? [[String: Any]] ?? []).compactMap { dict -> TaotieFolder? in
                guard let path = dict["path"] as? String else { return nil }
                return TaotieFolder(
                    path: path,
                    fileCount: dict["file_count"] as? Int ?? 0,
                    knowledgeFileCount: dict["knowledge_file_count"] as? Int ?? 0,
                    totalSize: dict["total_size"] as? Int ?? 0,
                    isAgentSession: dict["is_agent_session"] as? Bool ?? false,
                    isWechat: dict["is_wechat"] as? Bool ?? false,
                    checked: dict["checked"] as? Bool ?? true
                )
            }
            completion(.success(TaotieScanResult(files: files, folders: folders)))
        }.resume()
    }

    func taotieQueueState(completion: @escaping (Result<TaotieQueueState, Error>) -> Void) {
        let url = baseURL.appendingPathComponent("taotie/queue")
        session.dataTask(with: url) { data, _, _ in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let status = json["status"] as? String, status == "ok" else {
                completion(.failure(APIError.invalidResponse))
                return
            }
            let parseTasks: ([[String: Any]]) -> [TaotieTask] = { arr in
                arr.compactMap { dict -> TaotieTask? in
                    guard let path = dict["path"] as? String else { return nil }
                    return TaotieTask(
                        path: path,
                        size: dict["size"] as? Int ?? 0,
                        ext: dict["ext"] as? String ?? "",
                        selected: dict["selected"] as? Bool ?? true,
                        status: dict["status"] as? String ?? "pending",
                        progress: dict["progress"] as? Double ?? 0.0,
                        slug: dict["slug"] as? String ?? "",
                        error: dict["error"] as? String ?? ""
                    )
                }
            }
            completion(.success(TaotieQueueState(
                current: (json["current"] as? [String: Any]).flatMap { dict -> TaotieTask? in
                    guard let path = dict["path"] as? String else { return nil }
                    return TaotieTask(
                        path: path,
                        size: dict["size"] as? Int ?? 0,
                        ext: dict["ext"] as? String ?? "",
                        selected: dict["selected"] as? Bool ?? true,
                        status: dict["status"] as? String ?? "pending",
                        progress: dict["progress"] as? Double ?? 0.0,
                        slug: dict["slug"] as? String ?? "",
                        error: dict["error"] as? String ?? ""
                    )
                },
                pending: parseTasks(json["pending"] as? [[String: Any]] ?? []),
                done: parseTasks(json["done"] as? [[String: Any]] ?? []),
                error: parseTasks(json["error"] as? [[String: Any]] ?? []),
                skipped: parseTasks(json["skipped"] as? [[String: Any]] ?? []),
                paused: json["paused"] as? Bool ?? false,
                total: json["total"] as? Int ?? 0
            )))
        }.resume()
    }

    func taotieQueueStart(completion: @escaping (Result<String, Error>) -> Void) {
        post("/taotie/queue/start", body: [:]) { result in
            completion(result.map { _ in "started" })
        }
    }

    func taotieQueuePause(completion: @escaping (Result<String, Error>) -> Void) {
        post("/taotie/queue/pause", body: [:]) { result in
            completion(result.map { _ in "paused" })
        }
    }

    func taotieQueueClear(completion: @escaping (Result<String, Error>) -> Void) {
        post("/taotie/queue/clear", body: [:]) { result in
            completion(result.map { _ in "cleared" })
        }
    }

    func taotieQueueSelect(path: String, selected: Bool, completion: @escaping (Result<String, Error>) -> Void) {
        post("/taotie/queue/select", body: ["path": path, "selected": selected]) { result in
            completion(result.map { _ in "ok" })
        }
    }

    func taotieQueueRemove(path: String, completion: @escaping (Result<String, Error>) -> Void) {
        post("/taotie/queue/remove", body: ["path": path]) { result in
            completion(result.map { _ in "removed" })
        }
    }

    func taotieQueueAdd(files: [TaotieFile], completion: @escaping (Result<Int, Error>) -> Void) {
        let body: [String: Any] = [
            "files": files.map { ["path": $0.path, "size": $0.size, "ext": $0.ext] }
        ]
        post("/taotie/queue/add", body: body) { result in
            switch result {
            case .success(let data):
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let added = json["added"] as? Int {
                    completion(.success(added))
                } else {
                    completion(.failure(APIError.invalidResponse))
                }
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }

    func taotieHistory(limit: Int = 20, completion: @escaping ([TaotieHistoryRecord]) -> Void) {
        var components = URLComponents(url: baseURL.appendingPathComponent("taotie/history"), resolvingAgainstBaseURL: true)
        components?.queryItems = [URLQueryItem(name: "limit", value: String(limit))]
        guard let url = components?.url else {
            completion([])
            return
        }
        session.dataTask(with: url) { data, _, _ in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let records = json["records"] as? [[String: Any]] else {
                completion([])
                return
            }
            let mapped = records.compactMap { dict -> TaotieHistoryRecord? in
                guard let path = dict["path"] as? String else { return nil }
                return TaotieHistoryRecord(
                    path: path,
                    slug: dict["slug"] as? String ?? "",
                    status: dict["status"] as? String ?? "",
                    timestamp: dict["timestamp"] as? String ?? "",
                    error: dict["error"] as? String ?? ""
                )
            }
            completion(mapped)
        }.resume()
    }

    func taotieWatcher(completion: @escaping ([TaotieWatcherFolder]) -> Void) {
        let url = baseURL.appendingPathComponent("taotie/watcher")
        session.dataTask(with: url) { data, _, _ in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let folders = json["folders"] as? [[String: Any]] else {
                completion([])
                return
            }
            let mapped = folders.compactMap { dict -> TaotieWatcherFolder? in
                guard let path = dict["path"] as? String else { return nil }
                return TaotieWatcherFolder(
                    path: path,
                    enabled: dict["enabled"] as? Bool ?? true,
                    scanMode: dict["scan_mode"] as? String ?? "interval",
                    intervalHours: dict["interval_hours"] as? Int ?? 1,
                    dailyTime: dict["daily_time"] as? String ?? "02:00",
                    weeklyDay: dict["weekly_day"] as? Int ?? 0,
                    weeklyTime: dict["weekly_time"] as? String ?? "02:00"
                )
            }
            completion(mapped)
        }.resume()
    }

    func taotieWatcherAdd(path: String, completion: @escaping (Result<String, Error>) -> Void) {
        post("/taotie/watcher/add", body: ["path": path]) { result in
            completion(result.map { _ in "ok" })
        }
    }

    func taotieWatcherRemove(path: String, completion: @escaping (Result<String, Error>) -> Void) {
        post("/taotie/watcher/remove", body: ["path": path]) { result in
            completion(result.map { _ in "ok" })
        }
    }

    // MARK: - Private

    private func post(_ path: String, body: [String: Any], completion: @escaping (Result<Data, Error>) -> Void) {
        let url = baseURL.appendingPathComponent(path)
        os_log("post url=%{public}@", log: apiLog, type: .debug, url.absoluteString)

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        if request.httpBody == nil {
            os_log("post body serialization failed", log: apiLog, type: .error)
        }

        session.dataTask(with: request) { data, response, error in
            if let error = error {
                os_log("post network error=%{public}@", log: apiLog, type: .error, error.localizedDescription)
                completion(.failure(error))
                return
            }
            guard let data = data else {
                os_log("post no data, response=%{public}@", log: apiLog, type: .error, String(describing: response))
                completion(.failure(APIError.noData))
                return
            }
            os_log("post success dataLen=%d", log: apiLog, type: .debug, data.count)
            completion(.success(data))
        }.resume()
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

// MARK: - Taotie Models

struct TaotieFile: Identifiable {
    let id = UUID()
    let path: String
    let size: Int
    let ext: String
    var shouldIngest: Bool
    let reason: String
    let privacyLevel: String
    let containsPasswords: Bool
    let containsPII: Bool
    let isKnowledge: Bool
    var selected: Bool = true
}

struct TaotieFolder: Identifiable {
    let id = UUID()
    let path: String
    let fileCount: Int
    let knowledgeFileCount: Int
    let totalSize: Int
    let isAgentSession: Bool
    let isWechat: Bool
    var checked: Bool
}

struct TaotieScanResult {
    var files: [TaotieFile]
    var folders: [TaotieFolder]
}

struct TaotieTask: Identifiable {
    let id = UUID()
    let path: String
    let size: Int
    let ext: String
    var selected: Bool
    let status: String
    let progress: Double
    let slug: String
    let error: String
}

struct TaotieQueueState {
    var current: TaotieTask?
    var pending: [TaotieTask]
    var done: [TaotieTask]
    var error: [TaotieTask]
    var skipped: [TaotieTask]
    let paused: Bool
    let total: Int
}

struct TaotieHistoryRecord: Identifiable {
    let id = UUID()
    let path: String
    let slug: String
    let status: String
    let timestamp: String
    let error: String
}

struct TaotieWatcherFolder: Identifiable {
    let id = UUID()
    let path: String
    let enabled: Bool
    let scanMode: String
    let intervalHours: Int
    let dailyTime: String
    let weeklyDay: Int
    let weeklyTime: String
}

enum APIError: Error {
    case invalidURL
    case invalidResponse
    case noData
}
