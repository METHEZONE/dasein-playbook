// AI-ism lexicon, used only when an output has no slop spans from the scorer.
const LEX = ["truly transformative","rapidly evolving","delve","tapestry","it's worth","it is worth","in conclusion","ultimately","on the other hand","on one hand","cannot be overlooked","a reminder that","quietly special","dove into","navigat\\w+","exciting opportunit\\w+","meaningful moments","embrace the","unlock\\w*","game[- ]chang\\w+","testament to","looking forward to connecting","i would be delighted","truly a pleasure","energizing","right balance","more relevant than ever","landscape"];
const RE = new RegExp(`\\b(?:${LEX.join('|')})`, 'gi');
export function slopSpans(text) {
  return [...text.matchAll(RE)].map((m) => ({ start: m.index, end: m.index + m[0].length, kind: 'slop' }));
}
