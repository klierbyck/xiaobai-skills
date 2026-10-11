// macOS-only fallback: OCR pre-cropped subtitle frames, not a semantic summarizer.
// Usage: swift ocr_subtitles.swift FRAME_DIRECTORY OUTPUT_JSONL INTERVAL_SECONDS
import Foundation
import AppKit
import Vision

let args = CommandLine.arguments
guard args.count == 4, let interval = Double(args[3]), interval > 0 else {
    fputs("Usage: swift ocr_subtitles.swift FRAME_DIRECTORY OUTPUT_JSONL INTERVAL_SECONDS\n", stderr)
    exit(2)
}
let directory = URL(fileURLWithPath: args[1])
let output = URL(fileURLWithPath: args[2])
guard !FileManager.default.fileExists(atPath: output.path) else {
    fputs("Output exists; use a new path.\n", stderr); exit(2)
}
FileManager.default.createFile(atPath: output.path, contents: nil)
let handle = try FileHandle(forWritingTo: output)
let files = try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
    .filter { ["jpg", "png"].contains($0.pathExtension.lowercased()) }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }
for (index, file) in files.enumerated() {
    try autoreleasepool {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = true
        try VNImageRequestHandler(url: file, options: [:]).perform([request])
        let candidates = (request.results ?? []).compactMap { $0.topCandidates(1).first }
        let text = candidates.map { $0.string }.joined(separator: " ")
        let confidence = candidates.isEmpty ? 0 : candidates.map { $0.confidence }.reduce(0,+) / Float(candidates.count)
        // ffmpeg fps samples near the midpoint of each interval, approximate ±interval/2.
        let row: [String: Any] = ["sample_time_seconds": (Double(index)+0.5)*interval,
                                  "sample_uncertainty_seconds": interval/2,
                                  "file": file.lastPathComponent,
                                  "text": text, "confidence": confidence]
        let data = try JSONSerialization.data(withJSONObject: row, options: [.sortedKeys])
        handle.write(data); handle.write(Data("\n".utf8))
    }
    if index % 100 == 0 { print("OCR \(index+1)/\(files.count)") }
}
try handle.close()
print("Done \(files.count) subtitle samples")
