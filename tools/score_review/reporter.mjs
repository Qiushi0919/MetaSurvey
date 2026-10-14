// Node event reporter gives registered cases an identity even when parameter labels coincide.
export default async function* reporter(events){for await(const e of events){if(['test:pass','test:fail','test:summary'].includes(e.type))yield JSON.stringify({type:e.type,data:e.data})+'\n';}}
