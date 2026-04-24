
const fs = require('fs');
const path = require('path');

const src = '/home/featurize/work/BS/backend/frontend';
const dest = '/home/featurize/work/BS/frontend';

try {
  fs.renameSync(src, dest);
  console.log('Moved successfully');
} catch (err) {
  console.error('Error moving folder:', err);
}
