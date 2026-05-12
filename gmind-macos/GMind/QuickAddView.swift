import SwiftUI

struct QuickAddView: View {
    let onClose: () -> Void
    
    @State private var content = ""
    @State private var title = ""
    @State private var source = ""
    @State private var autoExtract = true
    @State private var isSubmitting = false
    @State private var statusMessage = ""
    @State private var showSuccess = false
    
    var body: some View {
        VStack(spacing: 16) {
            // Header
            HStack {
                Text("📝 Quick Add")
                    .font(.headline)
                Spacer()
                Button(action: onClose) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
            
            // Title
            TextField("Title (optional)", text: $title)
                .textFieldStyle(.roundedBorder)
            
            // Content
            TextEditor(text: $content)
                .font(.body)
                .frame(minHeight: 120)
                .overlay(
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(Color.secondary.opacity(0.2), lineWidth: 1)
                )
                .overlay(
                    Group {
                        if content.isEmpty {
                            Text("What's on your mind?")
                                .foregroundStyle(.secondary)
                                .allowsHitTesting(false)
                        }
                    },
                    alignment: .topLeading
                )
            
            // Source
            TextField("Source URL (optional)", text: $source)
                .textFieldStyle(.roundedBorder)
                .font(.caption)
            
            // Options
            Toggle("Auto-extract entities & tags", isOn: $autoExtract)
                .font(.caption)
            
            // Status
            if !statusMessage.isEmpty {
                Text(statusMessage)
                    .font(.caption)
                    .foregroundStyle(showSuccess ? .green : .red)
            }
            
            Spacer()
            
            // Actions
            HStack {
                Button("Cancel") {
                    onClose()
                }
                .keyboardShortcut(.escape, modifiers: [])
                
                Spacer()
                
                Button(action: submit) {
                    if isSubmitting {
                        ProgressView()
                            .scaleEffect(0.6)
                    } else {
                        Text("Save")
                    }
                }
                .keyboardShortcut(.return, modifiers: [.command])
                .disabled(content.isEmpty || isSubmitting)
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
        .frame(width: 440, height: 340)
    }
    
    private func submit() {
        isSubmitting = true
        statusMessage = ""
        
        GMindAPI.shared.addPage(content: content, title: title.isEmpty ? nil : title, source: source.isEmpty ? nil : source) { result in
            DispatchQueue.main.async {
                isSubmitting = false
                switch result {
                case .success(let slug):
                    showSuccess = true
                    statusMessage = "✅ Saved as [[\(slug)]]"
                    // Auto-clear after success
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                        content = ""
                        title = ""
                        source = ""
                        statusMessage = ""
                        onClose()
                    }
                case .failure(let error):
                    showSuccess = false
                    statusMessage = "❌ \(error.localizedDescription)"
                }
            }
        }
    }
}

#Preview {
    QuickAddView(onClose: {})
}
