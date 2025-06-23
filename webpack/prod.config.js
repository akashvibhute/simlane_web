const { merge } = require('webpack-merge');
const commonConfig = require('./common.config');

// This variable should mirror the one from config/settings/production.py
const s3BucketName = process.env.DJANGO_AWS_STORAGE_BUCKET_NAME;
const awsS3Domain = process.env.DJANGO_AWS_S3_CUSTOM_DOMAIN
  ? process.env.DJANGO_AWS_S3_CUSTOM_DOMAIN
  : `${s3BucketName}.s3.amazonaws.com`;
const staticUrl = `https://${awsS3Domain}/static/`;

module.exports = merge(commonConfig, {
  mode: 'production',
  devtool: 'source-map',
  bail: true,
  output: {
    publicPath: `${staticUrl}webpack_bundles/`,
  },
  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        // Alpine.js goes into vendor bundle (shared across all pages)
        vendor: {
          test: /[\\/]node_modules[\\/](alpinejs)[\\/]/,
          name: 'vendor',
          priority: 10,
        },
        // FullCalendar modules stay in their own chunk
        fullcalendar: {
          test: /[\\/]node_modules[\\/]@fullcalendar[\\/]/,
          name: 'fullcalendar',
          priority: 8,
        },
        // D3.js modules stay in their own chunk
        d3: {
          test: /[\\/]node_modules[\\/]d3[\\/]/,
          name: 'd3',
          priority: 8,
        },
      },
    },
  },
});
