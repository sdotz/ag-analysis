import Foundation

enum Gender: String, CaseIterable, Identifiable {
    case male = "male"
    case female = "female"

    var id: Self { self }

    var title: String {
        switch self {
        case .male: return "Male"
        case .female: return "Female"
        }
    }
}

enum RaceSurface: String, CaseIterable, Identifiable {
    case road = "road"
    case track = "track"

    var id: Self { self }

    var title: String {
        switch self {
        case .road: return "Road"
        case .track: return "Track"
        }
    }
}

final class AgeGradeCalculator {
    private struct Table {
        let maleWR: Double
        let femaleWR: Double
        let maleFactors: [Int: Double]
        let femaleFactors: [Int: Double]
    }

    static let shared = AgeGradeCalculator()

    private var tables: [Double: Table] = [:]

    private static let fileNameToMeters: [String: Double] = [
        "AgeGrade.1mi":  1609.344,
        "AgeGrade.4mi":  6437.376,
        "AgeGrade.5mi":  8046.72,
        "AgeGrade.5k":   5000,
        "AgeGrade.6k":   6000,
        "AgeGrade.8k":   8000,
        "AgeGrade.10k":  10000,
        "AgeGrade.10mi": 16093.44,
        "AgeGrade.12k":  12000,
        "AgeGrade.15k":  15000,
        "AgeGrade.20k":  20000,
        "AgeGrade.25k":  25000,
        "AgeGrade.30k":  30000,
        "AgeGrade.42k":  42195,
        "AgeGrade.50k":  50000,
        "AgeGrade.50mi": 80467.2,
        "AgeGrade.100k": 100000,
        "AgeGrade.100mi":160934.4,
        "AgeGrade.150k": 150000,
        "AgeGrade.200k": 200000,
        "AgeGrade.hm":   21097.5,
    ]

    private init() {
        load()
    }

    struct Result {
        /// The age grade factor for the given age (values < 1 indicate performance decline with age).
        let factor: Double
        /// Age graded mark: the open-age equivalent of the performance (timeSeconds * factor).
        let ageGradedMarkSeconds: Double
        /// Performance expressed as a percentage of the age standard (higher = better).
        let percentage: Double
    }

    func result(distanceMeters: Double, timeSeconds: Double, age: Int, gender: Gender) -> Result? {
        guard let table = nearestTable(for: distanceMeters) else { return nil }
        let wr = gender == .male ? table.maleWR : table.femaleWR
        let factors = gender == .male ? table.maleFactors : table.femaleFactors
        guard let factor = factors[age], factor > 0, timeSeconds > 0 else { return nil }
        let ageStandard = wr / factor
        let ageGradedMark = timeSeconds * factor
        return Result(factor: factor, ageGradedMarkSeconds: ageGradedMark, percentage: (ageStandard / timeSeconds) * 100)
    }

    private func nearestTable(for meters: Double) -> Table? {
        // Allow a small tolerance for floating point distances
        if let exact = tables[meters] { return exact }
        let tolerance = 0.5
        return tables.first { abs($0.key - meters) < tolerance }?.value
    }

    private func load() {
        // Try subdirectory first (preserved folder structure), fall back to bundle root.
        let subdirURLs = Bundle.main.urls(forResourcesWithExtension: nil, subdirectory: "RunScore") ?? []
        if !subdirURLs.isEmpty {
            for url in subdirURLs {
                let name = url.lastPathComponent
                guard let meters = Self.fileNameToMeters[name] else { continue }
                guard let table = parseTable(url: url) else { continue }
                tables[meters] = table
            }
            return
        }
        // Fallback: files were flattened to bundle root.
        for name in Self.fileNameToMeters.keys {
            guard let url = Bundle.main.url(forResource: name, withExtension: nil) else { continue }
            guard let meters = Self.fileNameToMeters[name] else { continue }
            guard let table = parseTable(url: url) else { continue }
            tables[meters] = table
        }
    }

    private func parseTable(url: URL) -> Table? {
        guard let contents = try? String(contentsOf: url, encoding: .utf8) else { return nil }
        let lines = contents.split(whereSeparator: \.isNewline).map(String.init)

        var maleWR: Double?
        var femaleWR: Double?
        var maleFactors: [Int: Double] = [:]
        var femaleFactors: [Int: Double] = [:]

        for line in lines {
            let parts = line.split(separator: " ", omittingEmptySubsequences: true).map(String.init)
            guard parts.count >= 2 else { continue }
            let genderToken = parts[0]

            if parts.count == 2 {
                // World record line: "M  0:12:49"
                if let seconds = parseTime(parts[1]) {
                    if genderToken == "M" { maleWR = seconds }
                    else if genderToken == "F" { femaleWR = seconds }
                }
            } else if parts.count == 3 {
                // Age factor line: "M 50 0.8761"
                guard let age = Int(parts[1]), let factor = Double(parts[2]) else { continue }
                if genderToken == "M" { maleFactors[age] = factor }
                else if genderToken == "F" { femaleFactors[age] = factor }
            }
        }

        guard let mwr = maleWR, let fwr = femaleWR,
              !maleFactors.isEmpty, !femaleFactors.isEmpty
        else { return nil }

        return Table(maleWR: mwr, femaleWR: fwr, maleFactors: maleFactors, femaleFactors: femaleFactors)
    }

    private func parseTime(_ text: String) -> Double? {
        let parts = text.split(separator: ":").map(String.init)
        guard parts.count == 2 || parts.count == 3 else { return nil }
        let numbers = parts.compactMap { Double($0) }
        guard numbers.count == parts.count else { return nil }
        if numbers.count == 2 { return numbers[0] * 60 + numbers[1] }
        return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    }
}
