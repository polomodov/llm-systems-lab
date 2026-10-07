
#include <metal_stdlib> 
#include <metal_tensor> 
#include <MetalPerformancePrimitives/MetalPerformancePrimitives.h> 
 
using namespace metal; 
using namespace mpp::tensor_ops; 
 
kernel void dummy_kernel( 
    tensor<device  half, dextents<int32_t, 2>> A [[buffer(0)]], 
    tensor<device  half, dextents<int32_t, 2>> B [[buffer(1)]], 
    device float * C [[buffer(2)]], 
    uint2 tgid [[threadgroup_position_in_grid]]) 
{ 
    auto tA = A.slice(0, (int)tgid.y); 
    auto tB = B.slice((int)tgid.x, 0); 
 
    matmul2d< 
        matmul2d_descriptor(16, 16, dynamic_extent), 
        execution_simdgroups<4>> mm; 
 
    auto cT = mm.get_destination_cooperative_tensor<decltype(tA), decltype(tB), float>(); 
 
    auto sA = tA.slice(0, 0); 
    auto sB = tB.slice(0, 0); 
    mm.run(sB, sA, cT); 
 
    auto tC = tensor<device float, dextents<int32_t, 2>, tensor_inline>(C, dextents<int32_t, 2>(4, 4)); 
 
    cT.store(tC); 
}