import os
import torch
from PIL import Image, UnidentifiedImageError
from torchvision import transforms
from torchvision.utils import save_image

# Adjusted imports for mainproject structure
from app.ai.models.adain.net import Encoder, decoder, vgg, adaptive_instance_normalization

class AdaINInference:
    def __init__(self, vgg_path, decoder_path, device=None):
        """
        Initializes the model architecture and loads pretrained weights.
        Automatically falls back to CPU if CUDA is unavailable.
        """
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device
            
        print(f"Loading AdaIN model onto: {self.device}")
        
        # Validate that the requested models exist
        if not os.path.exists(vgg_path):
            raise FileNotFoundError(f"VGG Normalised model not found at {vgg_path}")
        if not os.path.exists(decoder_path):
            raise FileNotFoundError(f"Decoder model not found at {decoder_path}")
            
        # Initialize network arch
        self.decoder = decoder
        self.vgg = vgg

        # Load weights reliably
        self.decoder.eval()
        self.vgg.eval()

        self.decoder.load_state_dict(torch.load(decoder_path, map_location=self.device))
        self.vgg.load_state_dict(torch.load(vgg_path, map_location=self.device))

        # Wrap into encoder
        self.encoder = Encoder(self.vgg)
        
        # Send to defined device
        self.encoder.to(self.device)
        self.decoder.to(self.device)

    def preprocess(self, img_path, size=512):
        """
        Resize and normalisation.
        Converts a PIL image to a proper tensor for the AdaIN network.
        """
        try:
            if isinstance(img_path, str):
                img = Image.open(img_path).convert("RGB")
            else:
                # Handle bytes or file-like objects if necessary
                img = Image.open(img_path).convert("RGB")
        except UnidentifiedImageError:
            raise ValueError(f"Could not load image file from path: {img_path}")
            
        # Optional: scale down if too large, while maintaining aspect ratio
        w, h = img.size
        # The shortest side becomes `size`
        scale = size / min(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
        transform = transforms.Compose([
            transforms.ToTensor(),
            # No ImageNet mean/std normalize because AdaIN uses normalized VGG weights directly!
        ])
        
        tensor = transform(img).unsqueeze(0)
        return tensor.to(self.device)

    def style_transfer(self, content_tensor, style_tensor, alpha=1.0):
        """
        Executes the exact AdaIN inference loop.
        alpha (float): style strength control (0.0 means original content, 1.0 means full style).
        """
        with torch.no_grad():
            # Extract features from VGG (up to relu4_1)
            content_f = self.encoder(content_tensor)
            style_f = self.encoder(style_tensor)
            
            # Apply AdaIN transform
            feat = adaptive_instance_normalization(content_f, style_f)
            
            # Allow partial style transfer blending
            # Formula: t = alpha * target_feature + (1 - alpha) * content_feature
            feat = feat * alpha + content_f * (1.0 - alpha)
            
            # Decode features back to pixel space
            return self.decoder(feat)
            
            
_adain_model_instance = None

def get_adain_model():
    global _adain_model_instance
    if _adain_model_instance is None:
        # Adjusted path for mainproject checkpoints
        # __file__ is mainproject/backend/app/ai/inference_adain.py
        ai_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(ai_dir)
        backend_dir = os.path.dirname(app_dir)
        
        checkpoints_dir = os.path.join(backend_dir, "checkpoints")
        vgg_weights = os.path.join(checkpoints_dir, "vgg_normalised.pth")
        decoder_weights = os.path.join(checkpoints_dir, "decoder.pth")
        _adain_model_instance = AdaINInference(vgg_path=vgg_weights, decoder_path=decoder_weights)
    return _adain_model_instance

def stylize(content_path, style_path, alpha=1.0):
    """
    Stand-alone helper function that reads two paths, processes them, 
    and saves the output stylized image, as requested.
    """
    # Init inference via global singleton
    model = get_adain_model()
    
    # Preprocess (automatically validates and reads paths)
    content_tensor = model.preprocess(content_path)
    style_tensor = model.preprocess(style_path)
    
    # Stylize
    output_tensor = model.style_transfer(content_tensor, style_tensor, alpha=alpha)
    
    # Ensure outputs array exists
    ai_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(ai_dir)
    backend_dir = os.path.dirname(app_dir)
    
    outputs_dir = os.path.join(backend_dir, "outputs")
    os.makedirs(outputs_dir, exist_ok=True)
    
    # Postprocessing: Tensor -> Image and save
    import uuid
    out_filename = f"stylized_{uuid.uuid4().hex}.jpg"
    out_path = os.path.join(outputs_dir, out_filename)
    
    # Convert and save
    save_image(output_tensor, out_path)
    print(f"Successfully stylized! Output saved to: {out_path}")
    return out_path
