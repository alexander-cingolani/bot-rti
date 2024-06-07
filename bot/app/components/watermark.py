from PIL import Image
import io


def add_watermark(
    stream: io.BytesIO, watermark_image_path: str = "./app/assets/images/rti.png"
) -> io.BytesIO:
    """Adds a watermark to a bitmap image and returns the watermarked bitmap.

    Args:
        input_image (Image): A PIL Image object of the input image.
        watermark_image_path (str): The path to the watermark image file, default is
                                    '/assets/images/rti.png'.

    Returns:
        Image: A PIL Image object of the watermarked image.

    Raises:
        ValueError: If the watermark image is larger than the input image.
    """

    input_image = Image.open(stream)

    watermark = Image.open(watermark_image_path)
    watermark.resize((750, 253))
    # Ensure the watermark isn't larger than the base image
    if (
        watermark.size[0] > input_image.size[0]
        or watermark.size[1] > input_image.size[1]
    ):
        raise ValueError(
            "The watermark image is too large. Please use a smaller image or resize the input image."
        )

    # Paste the watermark onto the base image, assuming bottom-right corner placement
    position = (
        input_image.size[0] - watermark.size[0] - 75,
        input_image.size[1] - watermark.size[1] - 75,
    )
    input_image.paste(watermark, position, watermark)

    output_stream = io.BytesIO()
    input_image.save(output_stream, format="PNG")
    output_stream.seek(0)

    return output_stream
