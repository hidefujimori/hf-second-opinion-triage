import RadioBar from '@splunk/react-ui/RadioBar';

// "日本語 (JA)": the "(JA)" part stays readable where no Japanese font is installed
// (the Japanese characters would show as boxes there). Tooltip / screen reader: "Japanese".
export default function LangSwitch({ lang, onChange }) {
  return (
    <RadioBar value={lang} onChange={(e, { value }) => onChange(value)} style={{ width: 200 }} aria-label="Language">
      <RadioBar.Option value="en" label="English" title="English" lang="en" />
      <RadioBar.Option value="ja" label="日本語 (JA)" title="Japanese" aria-label="Japanese" lang="ja" />
    </RadioBar>
  );
}
