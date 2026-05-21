import Foundation

struct EntitySummary: Codable, Identifiable, Hashable, Sendable {
    let id: Int
    let name: String
    let entityType: String
    let status: String
    let claimCount: Int
    let eventCount: Int

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case entityType = "entity_type"
        case status
        case claimCount = "claim_count"
        case eventCount = "event_count"
    }
}

struct ClaimSummary: Codable, Identifiable, Hashable, Sendable {
    let id: Int
    let text: String
    let claimType: String
    let origin: String
    let status: String
    let confidence: Double?

    enum CodingKeys: String, CodingKey {
        case id
        case text
        case claimType = "claim_type"
        case origin
        case status
        case confidence
    }
}

struct EventSummary: Codable, Identifiable, Hashable, Sendable {
    let id: Int
    let eventType: String
    let title: String
    let occurredAt: String?
    let confidence: Double?

    enum CodingKeys: String, CodingKey {
        case id
        case eventType = "event_type"
        case title
        case occurredAt = "occurred_at"
        case confidence
    }
}

struct TaskSummary: Codable, Identifiable, Hashable, Sendable {
    let id: Int
    let taskType: String
    let title: String
    let status: String
    let priority: Int
    let nextRunAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case taskType = "task_type"
        case title
        case status
        case priority
        case nextRunAt = "next_run_at"
    }
}

struct RelationSummary: Codable, Identifiable, Hashable, Sendable {
    let id: Int
    let subjectType: String
    let subjectId: Int
    let predicate: String
    let objectType: String
    let objectId: Int
    let confidence: Double?

    enum CodingKeys: String, CodingKey {
        case id
        case subjectType = "subject_type"
        case subjectId = "subject_id"
        case predicate
        case objectType = "object_type"
        case objectId = "object_id"
        case confidence
    }
}

struct EntityDetail: Codable, Identifiable, Hashable, Sendable {
    let id: Int
    let name: String
    let entityType: String
    let description: String?
    let status: String
    let claims: [ClaimSummary]
    let events: [EventSummary]
    let tasks: [TaskSummary]
    let relations: [RelationSummary]

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case entityType = "entity_type"
        case description
        case status
        case claims
        case events
        case tasks
        case relations
    }
}

struct CommandResult: Sendable {
    let status: Int32
    let output: String
    let error: String

    var succeeded: Bool {
        status == 0
    }

    var humanMessage: String {
        if succeeded {
            return output.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        let message = error.isEmpty ? output : error
        return message.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

struct ConnectionCheckResult: Sendable {
    let command: CommandResult
    let entities: [EntitySummary]
}

struct SoloSettings: Sendable {
    var enabled: Bool
}

struct AskResult: Sendable {
    let answer: String
    let evidenceChips: [String]
    let entities: [EntitySummary]
}

struct AskCLIResponse: Codable, Sendable {
    let question: String
    let answer: String
    let evidence: [AskEvidence]
    let followups: [String]
}

struct AskEvidence: Codable, Sendable {
    let sourceId: Int
    let chunkId: Int
    let title: String
    let text: String
    let score: Double

    enum CodingKeys: String, CodingKey {
        case sourceId = "source_id"
        case chunkId = "chunk_id"
        case title
        case text
        case score
    }
}
