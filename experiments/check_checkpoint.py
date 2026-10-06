import torch

checkpoint_path = "checkpoints/baseline_fused_best.pth"

checkpoint = torch.load(
    checkpoint_path,
    map_location="cpu",
    weights_only=False
)

print("Checkpoint contents:")
print(checkpoint.keys())

print("\nEpoch:", checkpoint.get("epoch"))

print("\nAll checkpoint information:")
for key, value in checkpoint.items():
    if not isinstance(value, dict):
        print(key, ":", value)