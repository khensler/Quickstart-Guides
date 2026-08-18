| Backend | Array | `backend` parameter | Unit provisioned per PVC | Primary use |
|---|---|---|---|---|
| FlashBlade Direct Access | FlashBlade | `pure_file` | A FlashBlade file system | Large shared datasets, image registry, AI/ML, analytics |
| FlashArray File Services | FlashArray | `pure_fa_file` | A managed directory in an existing file system | RWX volumes alongside block workloads on an array you already own |

Choose FlashBlade when the workload is throughput-oriented or the dataset is large and shared. Choose FlashArray File Services when you want RWX file storage from the same FlashArray already serving block volumes, and you can accept its snapshot and quota limitations.
