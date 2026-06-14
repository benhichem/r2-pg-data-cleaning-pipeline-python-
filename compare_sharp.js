import sharp from "sharp";
import fs from "fs";

const imagePath = process.argv[2];
if (!imagePath) {
  console.error("Please provide an image path");
  process.exit(1);
}

async function run() {
  const imageBuffer = fs.readFileSync(imagePath);
  const { data, info } = await sharp(imageBuffer)
    .resize(150, 150, { fit: "fill" })
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const total = info.width * info.height;
  let navyCount = 0;
  let lightBlueCount = 0;

  for (let i = 0; i < data.length; i += 3) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];

    if (r < 80 && g < 80 && b > 80) navyCount++;
    if (r > 180 && g > 190 && b > 210 && b > r && b > g) lightBlueCount++;
  }

  const navyPct = (navyCount / total) * 100;
  const lightBluePct = (lightBlueCount / total) * 100;

  console.log(`SHARP RESULTS for ${imagePath}:`);
  console.log(`Total pixels: ${total}`);
  console.log(`Navy pixels : ${navyCount} (${navyPct.toFixed(2)}%)`);
  console.log(`L-Blue pixels: ${lightBlueCount} (${lightBluePct.toFixed(2)}%)`);
  console.log(`Is Placeholder: ${navyPct >= 20 && lightBluePct >= 20}`);
}

run().catch(console.error);
