from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="GTSinger/GTSinger",
    repo_type="dataset",
    local_dir="/home/featurize/data/GTSinger",
)
print("download done")
