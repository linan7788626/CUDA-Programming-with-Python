import pycuda.autoinit
import pycuda.driver as drv
import numpy, math, sys
from pycuda.compiler import DynamicSourceModule

if len(sys.argv)>2 and sys.argv[1]=='-double':
    real_py = 'float64' 
    real_cpp = 'double'
else:
    real_py = 'float32'
    real_cpp = 'float'

mod = DynamicSourceModule(r"""
void __global__ reduce(const real *d_x, real *d_y, const int N)
{
    const int tid = threadIdx.x;
    const int bid = blockIdx.x;
    const int n = bid * blockDim.x + tid;
    extern __shared__ real s_y[];
    s_y[tid] = (n < N) ? d_x[n] : 0.0;
    __syncthreads();

    for (int offset = blockDim.x >> 1; offset > 0; offset >>= 1)
    {
        if (tid < offset)
        {
            s_y[tid] += s_y[tid + offset];
        }
        __syncthreads();
    }

    if (tid == 0)
    {
        atomicAdd(d_y, s_y[0]);
    }
}""".replace('real', real_cpp))
reducef = mod.get_function("reduce")



def timing():
    NUM_REPEATS = 10
    N = 100000000
    BLOCK_SIZE = 128
    grid_size = (N-1)//128+1
    h_x = numpy.full((N,1), 1.23, dtype=real_py)
    d_x = drv.mem_alloc(h_x.nbytes)
    drv.memcpy_htod(d_x, h_x)
    size_real = numpy.dtype(real_py).itemsize
    t_sum = 0
    t2_sum = 0
    for repeat in range(NUM_REPEATS+1):
        start = drv.Event()
        stop = drv.Event()
        start.record()
        h_y = numpy.zeros((1,1), dtype=real_py)
        d_y = drv.mem_alloc(h_y.nbytes)
        drv.memcpy_htod(d_y, h_y)
        reducef(
            d_x, 
            d_y, 
            numpy.int32(N), 
            grid=(grid_size, 1), 
            block=(128,1,1), 
            shared=size_real*BLOCK_SIZE
            )

        drv.memcpy_dtoh(h_y, d_y)
        v_sum = h_y[0,0]
        
        stop.record()
        stop.synchronize()
        elapsed_time = start.time_till(stop)
        print("Time = {:.6f} ms.".format(elapsed_time))
        if repeat > 0:
            t_sum += elapsed_time
            t2_sum += elapsed_time * elapsed_time
    t_ave = t_sum / NUM_REPEATS
    t_err = math.sqrt(t2_sum / NUM_REPEATS - t_ave * t_ave)
    print("Time = {:.6f} +- {:.6f} ms.".format(t_ave, t_err))
    print("sum = ", v_sum)
    

print("using atomicAdd:")
timing()