#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc != 3) return 64;
        NSError *error = nil;
        NSString *source = [NSString stringWithContentsOfFile:@(argv[1])
                                                   encoding:NSUTF8StringEncoding error:&error];
        if (!source) { NSLog(@"source error: %@", error); return 1; }
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) return 2;
        MTLCompileOptions *options = [MTLCompileOptions new];
        options.preprocessorMacros = @{};
        NSString *mode = @(argv[2]);
        if ([mode isEqualToString:@"3.2"]) options.languageVersion = MTLLanguageVersion3_2;
        else if ([mode isEqualToString:@"4.0"]) options.languageVersion = MTLLanguageVersion4_0;
        else if (![mode isEqualToString:@"default"]) return 64;
        printf("device=%s mode=%s languageVersion=%lu Metal4=%d Apple10=%d\n",
               device.name.UTF8String, mode.UTF8String, (unsigned long)options.languageVersion,
               [device supportsFamily:MTLGPUFamilyMetal4], [device supportsFamily:MTLGPUFamilyApple10]);
        id<MTLLibrary> library = [device newLibraryWithSource:source options:options error:&error];
        if (!library) {
            fprintf(stderr, "library error: %s\n", error.description.UTF8String);
            return 3;
        }
        if (error) fprintf(stderr, "library warning: %s\n", error.description.UTF8String);
        error = nil;
        id<MTLFunction> function = [library newFunctionWithName:@"dummy_kernel"];
        id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:function error:&error];
        if (!pipeline) {
            fprintf(stderr, "pipeline error: %s\n", error.description.UTF8String);
            return 4;
        }
        printf("library=ok pipeline=ok executionWidth=%lu maxThreads=%lu\n",
               (unsigned long)pipeline.threadExecutionWidth,
               (unsigned long)pipeline.maxTotalThreadsPerThreadgroup);
        return 0;
    }
}
