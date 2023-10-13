import os
import subprocess
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


load_type = {
    'SEQ_READ': 0, 
    'SEQ_WRITE':1, 
    'RAND_READ': 2, 
    'RAND_WRITE': 3}

# Other GDSIO xfer_types:
# 'Storage->CPU': 1, 
# 'Storage->CPU-GPU_ASYNC': 3,
# 'Storage->PAGE_CACHE->CPU->GPU': 4,
# 'Storage->GPU_ASYNC': 5,
# 'STORAGE->GPU_BATCH': 6,
transfer_type = { 
    'Storage->GPU (GDS)': 0, 
    'Storage->CPU->GPU': 2, 
    } 

gdsio_path = '/usr/local/cuda-12.0/gds/tools/gdsio' # PATH for gdsio
gds_dir = '/home/n4/jaehwan/project/nvidia-gpudirect-example/gds_files' # NVMe mounted location
device = 0
numa_node = 0
load = 'SEQ_READ'


def init_gds_files(gdsio_path, output_dir, file_size, device, workers):
    ''' To do read tests, write test must be done first with correct number of workers and file size '''

    # Just do a random write with the correct number of workers, will generate gdsio.[0 - <workers - 1>].
    cmd = [
        'sudo', gdsio_path, 
        '-D', output_dir, # Mount file location
        '-d', device, # GPU index
        '-s', file_size, # Target file size
        '-w', workers, # Number of IO threads
        '-I', 1, # <(read)0|(write)1|(randread)2|(randwrite)3>
        '-V' # IO Verification 
        ] 
    cmd = [str(x) for x in cmd]
    subprocess.run(cmd)


def gds_benchmark(gdsio_path, output_dir, device, numa_node, load):
    file_size = '1G'
    io_sizes = ['128K', '256K', '512K', '1M'] # ['128K', '256K', '512K', '1M', '4M', '16M', '64M', '128M']
    threads = [1, 4, 8, 16, 32]
    time = '10'
    
    # See if benchmark files need to be generated.
    if not os.path.isfile(os.path.join(output_dir, f'gdsio.{max(threads) - 1}')):
        print("Writing gds files...")
        init_gds_files(gdsio_path, output_dir, file_size, device, max(threads))

    res_dict = {
        'Transfer Type': [], 
        'Threads': [], 
        'Throughput (GiB/s)': [], 
        'Latency (usec)': [], 
        'IO Size': []
        }
    
    # With '-V' option '-T' (timed) option is ignored.  
    base_cmd = [
        'sudo', gdsio_path, 
        '-D', output_dir, 
        '-d', device, 
        '-n', numa_node, 
        '-T', time, 
        '-s', file_size, 
        '-V'
        ]  
    
    print("Start Reading gds files...")
    for io_size in io_sizes:
        for thread in threads:
            for transfer_name, x in transfer_type.items():
                new_cmd = base_cmd + ['-i', io_size] + ['-w', thread] + ['-x', x] + ['-I', load_type[load]]
                new_cmd = [str(x) for x in new_cmd]
                
                print('Running', new_cmd)
                res = subprocess.run(new_cmd, capture_output=True).stdout
                res = str(res).split(' ')
                latency = float(res[res.index('Avg_Latency:') + 1])
                throughput = float(res[res.index('Throughput:') + 1])
                print('latency', latency, 'throughput', throughput)

                res_dict['Transfer Type'].append(transfer_name)
                res_dict['Threads'].append(thread)
                res_dict['IO Size'].append(io_size)
                res_dict['Latency (usec)'].append(latency)
                res_dict['Throughput (GiB/s)'].append(throughput)
    print("Finished!")

    df = pd.DataFrame.from_dict(res_dict)
    df.to_csv(f'gds_bench_save_device_{device}_numa_{numa_node}_{load}.csv')


def plot_results(device, numa_node, load):
    df = pd.read_csv(f'gds_bench_save_device_{device}_numa_{numa_node}_{load}.csv')
    
    g = sns.catplot(df, kind='bar', 
                        x='Threads', 
                        y='Latency (usec)', 
                        col='IO Size', 
                        hue='Transfer Type', 
                        sharey=False)
    g.figure.savefig('image/gds_plot_latency.png')
    g = sns.catplot(df, kind='bar', 
                        x='Threads', 
                        y='Throughput (GiB/s)', 
                        col='IO Size', 
                        hue='Transfer Type', 
                        sharey=False)
    g.figure.savefig('image/gds_plot_throughput.png')


if __name__ == '__main__':
    gds_benchmark(gdsio_path, gds_dir, device, numa_node, load)
    plot_results(device, numa_node, load)