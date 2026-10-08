// Build: copy package.json + this file to a build folder, `npm install`, then
//   UI_SRC=<path to ui/src> APP_DIR=<path to TA-jev-triage> npx webpack --mode production
const path = require('path');
const SRC = process.env.UI_SRC || path.join(__dirname, 'src');
const APP = process.env.APP_DIR || path.join(__dirname, '..', 'TA-jev-triage');
module.exports = {
  // bundle names = view names: the built-in view template pages/splunk_ui_app.html loads pages/<view>.js
  entry: { jev_triage: path.join(SRC, 'pages/triage/index.jsx'), jev_setup: path.join(SRC, 'pages/setup/index.jsx') },
  output: { path: path.join(APP, 'appserver/static/pages'), filename: '[name].js', clean: false },
  resolve: { extensions: ['.js', '.jsx'], modules: [path.join(process.cwd(), 'node_modules'), 'node_modules'] },
  module: { rules: [{ test: /\.jsx?$/, exclude: /node_modules/, use: { loader: require.resolve('babel-loader'), options: {
    babelrc: false, configFile: false,
    presets: [[require.resolve('@babel/preset-env'), { targets: '> 0.5%, last 2 versions, not dead' }],
              [require.resolve('@babel/preset-react'), { runtime: 'automatic' }]] } } }] },
  // ascii_only: non-ASCII text (Japanese labels) is written as \uXXXX escapes, so the bundle is pure ASCII
  // and cannot be garbled if a browser or proxy guesses the wrong character set.
  optimization: { minimizer: [new (require(require.resolve('terser-webpack-plugin')))({
    extractComments: false, terserOptions: { format: { ascii_only: true } } })] },
  performance: { hints: false },
  devtool: false,
};
