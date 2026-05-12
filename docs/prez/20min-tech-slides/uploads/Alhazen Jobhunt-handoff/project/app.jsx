// App entry — design canvas with three dossier variants + triage inbox.
//
// Variants exercise the kind discriminator: position, engagement, venture.
// Same component, same shape, three different render outcomes.

const { useState, useEffect, useCallback } = React;

function App() {
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [schemaFocus, setSchemaFocus] = useState(null);

  useEffect(() => {
    window.__openSchema = (focus) => { setSchemaFocus(focus || null); setSchemaOpen(true); };
    const onKey = (e) => { if (e.key === 'Escape') setSchemaOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const position   = window.api.showOpportunity(window.OPP_IDS.position);
  const engagement = window.api.showOpportunity(window.OPP_IDS.engagement);
  const venture    = window.api.showOpportunity(window.OPP_IDS.venture);
  const attention  = window.api.listAttention();
  const dossierIds = Object.values(window.OPP_IDS);

  // Inbox → dossier handoff: clicking a row in the inbox opens that dossier
  // in the focus overlay. Maps opportunity id → artboard id.
  const idToArtboard = {
    [window.OPP_IDS.position]:   'dossier-position',
    [window.OPP_IDS.engagement]: 'dossier-engagement',
    [window.OPP_IDS.venture]:    'dossier-venture',
  };
  const onOpenFromInbox = useCallback((oppId) => {
    const slot = idToArtboard[oppId];
    if (slot && window.__dcSetFocus) window.__dcSetFocus(`dossiers/${slot}`);
  }, []);

  return (
    <>
      <DesignCanvas>
        <DCSection
          id="pipeline"
          title="In play — every lead you are actively working"
          subtitle="The leads you have committed attention to. Sorted by priority. Powered by list-attention."
        >
          <DCArtboard id="in-play" label="In play" width={1240} height={1100}>
            <window.TriageInbox items={attention} dossierIds={dossierIds} onOpen={onOpenFromInbox} />
          </DCArtboard>
        </DCSection>

        <DCSection
          id="dossiers"
          title="Lead dossier — three kinds, one shell"
          subtitle="Open one lead at a time. Same component dispatches on the type field from show-opportunity."
        >
          <DCArtboard id="dossier-position" label="Position · Augura Health" width={1240} height={1700}>
            <window.Dossier data={position} />
          </DCArtboard>
          <DCArtboard id="dossier-engagement" label="Engagement · Reseda Bio" width={1240} height={1450}>
            <window.Dossier data={engagement} />
          </DCArtboard>
          <DCArtboard id="dossier-venture" label="Venture · Project Kiln" width={1240} height={1400}>
            <window.Dossier data={venture} />
          </DCArtboard>
        </DCSection>
      </DesignCanvas>
      <window.SchemaInspector open={schemaOpen} focus={schemaFocus} onClose={() => setSchemaOpen(false)} />
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
