import SwiftUI

struct AskAIView: View {
    let onClose: () -> Void

    @State private var question = ""
    @State private var answer = ""
    @State private var sources: [Source] = []
    @State private var isThinking = false
    @State private var errorMessage = ""
    @FocusState private var isFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            // Search bar
            HStack(spacing: 10) {
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 14))
                    .foregroundStyle(.secondary)

                TextField("问你的知识库...", text: $question)
                    .textFieldStyle(.plain)
                    .font(.body)
                    .focused($isFocused)
                    .onSubmit { ask() }

                if isThinking {
                    ProgressView()
                        .scaleEffect(0.7)
                }

                Button(action: onClose) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 16))
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(.thinMaterial)

            Divider()

            // Content
            if !errorMessage.isEmpty {
                VStack {
                    Spacer()
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .font(.callout)
                    Spacer()
                }
                .padding()
            } else if !answer.isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        Text(answer)
                            .font(.body)
                            .lineSpacing(4)
                            .textSelection(.enabled)

                        if !sources.isEmpty {
                            VStack(alignment: .leading, spacing: 6) {
                                Divider()
                                Text("来源")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .padding(.top, 4)

                                ForEach(sources) { source in
                                    HStack(spacing: 4) {
                                        Text(source.title)
                                            .font(.caption)
                                            .foregroundColor(.blue)
                                        Text("(\(String(format: "%.2f", source.relevance)))")
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                    }
                    .padding(20)
                }
            } else {
                VStack {
                    Spacer()
                    Image(systemName: "brain.head.profile")
                        .font(.system(size: 40))
                        .foregroundStyle(.secondary.opacity(0.3))
                    Text("输入问题，按回车问 AI")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .padding(.top, 12)
                    Spacer()
                }
            }
        }
        .frame(width: 560, height: 480)
        .background(Color.clear)
        .onAppear {
            isFocused = true
        }
    }

    private func ask() {
        guard !question.isEmpty else { return }
        isThinking = true
        answer = ""
        sources = []
        errorMessage = ""

        GMindAPI.shared.ask(question: question, topK: 8) { result in
            DispatchQueue.main.async {
                isThinking = false
                switch result {
                case .success(let response):
                    answer = response.answer
                    sources = response.sources
                case .failure(let error):
                    errorMessage = error.localizedDescription
                }
            }
        }
    }
}
