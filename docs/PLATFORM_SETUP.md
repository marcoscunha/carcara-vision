# 🔧 Platform-Specific Setup

## 🚀 NVIDIA Jetson

```bash
# JetPack should be pre-installed with CUDA and TensorRT
sudo nvpmodel -m 0
sudo jetson_clocks

export ACCELERATOR=jetson
export TENSORRT_ENABLED=true
```

## 🍓 Raspberry Pi with Coral TPU

```bash
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt update
sudo apt install libedgetpu1-std python3-pycoral

export ACCELERATOR=rpi
export RPI_USE_CORAL_TPU=true
```

## 🍓 Raspberry Pi with Hailo-8

```bash
# Install Hailo runtime from the vendor documentation
export ACCELERATOR=rpi
export RPI_USE_HAILO=true
```
