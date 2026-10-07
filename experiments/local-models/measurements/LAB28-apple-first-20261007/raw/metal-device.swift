import Metal
import Foundation
guard let device = MTLCreateSystemDefaultDevice() else {
    fputs("Metal device unavailable\n", stderr)
    exit(1)
}
let data: [String: Any] = [
    "name": device.name,
    "has_unified_memory": device.hasUnifiedMemory,
    "recommended_max_working_set_bytes": device.recommendedMaxWorkingSetSize,
    "max_buffer_length_bytes": device.maxBufferLength
]
let encoded = try JSONSerialization.data(withJSONObject: data, options: [.prettyPrinted, .sortedKeys])
print(String(decoding: encoded, as: UTF8.self))
