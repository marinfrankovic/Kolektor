/**
 * Cheap focus check so the phone can warn before a blurry photo is uploaded.
 * Variance of a Laplacian on a downscaled greyscale copy.
 */
export async function blurScore(file: Blob): Promise<number> {
  const bitmap = await createImageBitmap(file);
  const side = 320;
  const scale = Math.min(side / bitmap.width, side / bitmap.height, 1);
  const width = Math.max(8, Math.round(bitmap.width * scale));
  const height = Math.max(8, Math.round(bitmap.height * scale));

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return Number.POSITIVE_INFINITY;

  context.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();

  const { data } = context.getImageData(0, 0, width, height);
  const grey = new Float32Array(width * height);
  for (let i = 0; i < grey.length; i += 1) {
    const p = i * 4;
    grey[i] = 0.299 * data[p] + 0.587 * data[p + 1] + 0.114 * data[p + 2];
  }

  let sum = 0;
  let sumSquares = 0;
  let count = 0;
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const i = y * width + x;
      const value =
        4 * grey[i] - grey[i - 1] - grey[i + 1] - grey[i - width] - grey[i + width];
      sum += value;
      sumSquares += value * value;
      count += 1;
    }
  }

  if (count === 0) return Number.POSITIVE_INFINITY;
  const mean = sum / count;
  return sumSquares / count - mean * mean;
}

export const BLUR_THRESHOLD = 60;
