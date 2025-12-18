Printing Data Squad
Cells only fail in a few ways, and they start failing long before they die.
That’s where intervention lives.
That’s what the tensor reveals.
“Failure is not an ending
It is a grammar with only a few verbs.
Cells conjugate their fate early,
Tracing futures into living matter.
We do not wait for the full stop.
We read the sentence as it forms.
That is what the tensor reveals.”

Hypothesis
The structure of cellular stress biology is low dimensional, conserved across lineagens, and discoverable if and only if you measure perturbations, cell types, and stressors on shared rails. 
Cells reuse a finite set of conserved programs to manage mitochondrial failures, ER burden, redox imbalance, lipid overload, lysosomal dysfunction and fibrotic signaling.
Lineage shapes the response but the core architecture is shared.


The architecture only becomes visible when you perturb the system.
Unstressed cells don’t tell you how they behave under pressure.


The current data landscape cannot reveal this structure
When datasets live in their own idiosyncratic worlds perturbational signatures are not comparable. You can’t see conserved patterns, lineage specificity or conditional phenotypes.    


A printed tensor will reveal it
If we measure the same perturbations, same stressors, same imaging recipe, the latent structure should surface:
Shared stress axes
Lineage-bound programs
Context-dependent regulators
    
Objective
Build a tractable, information-dense dataset that resolves how genes drive cellular stress responses across distinct lineages. We will generate a structured multi-axis tensor of cell line × stressor × perturbation × measurement using pooled optical screening (POSH) with a whole-genome library and insitro paint–derived readouts. 
The design also preserves optionality for FLEX-based Perturb-seq, which can be layered onto the same rails once the method reaches a comparable technology readiness level for routine deployment. This ensures that the POSH tensor can be complemented with transcriptomic resolution without redesigning the underlying experimental grid.
Context
Right now our pooled datasets are patchy: a few good runs, a few okay ones, and a lot of gaps. Most of the single-purpose screens made sense at the time but don’t align on a shared biological grid. A549, HepG2, and SH-SY5Y have whole-genome or near-whole-genome POSH data in some form, but each was run under different assumptions.
Some of the company’s most useful data come from focused libraries, druggable genome sets, custom pathway panels, or Perturb-seq follow-ups. They provide depth in isolated contexts, but the coverage across cell types and biological functions is too thin to connect the learnings from one screen to another or to relate controlled stress-axis biology back to disease models in a consistent way.
The models were also disease-oriented: FFA treatment, TDP43 siRNA,  designed to answer single-indication questions, not to map cross-cellular and biological network behavior.
The Gap
As a result, we can ask local questions, but not global ones, not yet.
We can’t easily answer:
Which stress axes are shared?
Which are lineage-specific?
Which gene programs only appear when a cell is hit with the right insult?
And perhaps the most basic, but most contested question: how much of a cell’s stress behavior is defined by its type, and how much by its state?
Our current corpus isn’t printed against:
a common panel of stressors
a coherent panel of cells
a stable imaging/readout recipe


Program Definition

What we are building
A printed, multi-axis tensor defined by cell line × stressor × perturbation × measurement.
A controlled, repeatable experimental grid that produces aligned POSH and Cell Painting readouts.
What it is for
To reveal the conserved and lineage-specific structure of cellular stress responses.
To create a stable biological coordinate system that future screens can map onto.
To turn disconnected datasets into cumulative knowledge.
What it is not
Not a disease model.
Not an exhaustive catalog of stressors.
Not a pharmacological survey.
Why this structure solves the gap
Current datasets cannot be compared because rails differ across lineage, stress, and readout.
A printed tensor standardizes these rails, making perturbational signatures interpretable across contexts.
It provides the foundation for models that learn biology instead of assay artifacts.

What we want instead
A printed tensor built on a small, principled set of biological rails that define the major stress axes:
mitochondrial dysfunction
ER stress and proteostasis
lipid handling
lysosomal and trafficking defects
fibrotic and ECM remodeling
oxidative response


They are the conserved response programs cells use to stabilize their internal state, adapt to external pressure, or transition into maladaptive failure modes. Taken together, these programs form the regulatory scaffold that disease processes either hijack broadly across lineages or distort in cell-type-specific way
With gene-level effects mapped across 3–5 diverse cell types, we can begin to make statements with actual structure:
This gene only contributes to oxidative rescue in liver-like cells.
This gene acts as an ER triage regulator across lineages.
This gene’s perturbational phenotype is restricted to neuronal contexts and is absent in epithelial systems.
This network may be particularly informative for dissecting fibrotic remodeling because it activates only under fibrotic stress in the relevant lineages and includes targets with probable druggability potential.
The Point of Printing Data
Take the messy, disease-driven, partly whole-genome, partly sublibrary corpus we already have. Add a clean, biologically structured slab of data that lets us assemble the first coherent multi-cell, multi-stressor map of cellular stress biology.
Why Now / Strategic Value to the Company

The existing pooled screens, focused libraries, and disease-model experiments have generated pockets of insight for specific therapeutic areas (TAs), but they do not compose. Each dataset lives on its own coordinate system, shaped by a different lineage, a different stressor, a different readout recipe, and a different set of implicit assumptions. This fragmentation prevents the organization from building general biological knowledge and forces every new analysis to begin from scratch.

A printed tensor addresses this directly by creating a shared experimental and analytical foundation. It becomes the first dataset that is intentionally structured to reveal conserved and lineage-specific stress biology across perturbations, cell types, and contexts. This structure unlocks several forms of value.

1. A unified biological coordinate system
The tensor provides a common set of biological rails that all future screens can attach to. Instead of one-off results, the company gains a stable reference frame for integrating historical and prospective data, enabling direct comparison across lineages and conditions.

2. A training substrate for representation learning
Most internal models suffer from sparse, uneven, or non-aligned inputs. A printed dataset solves this by offering dense, multi-axis coverage with synchronized perturbations and readouts. This is the level of structure required to train generalizable morphological and transcriptional embeddings that capture causal biology rather than assay artifacts.

3. A map of stress response architecture that generalizes across programs
Stress biology underlies lipid disorders, fibrosis, neurodegeneration, inflammatory remodeling, and many of our therapeutic areas. By mapping how genes regulate conserved axes like mitochondrial dysfunction, ER triage, redox management, and ECM remodeling, the tensor creates a reusable mechanistic scaffold that supports multiple discovery efforts simultaneously.

4. A framework for identifying tractable intervention points
By comparing perturbational fingerprints across lineages and stress conditions, the tensor highlights nodes that are conserved, context-dependent, or selectively vulnerable. This directly informs target nomination and the design of pathway-level therapeutic hypotheses.

5. A reduction in operational drift and analytical uncertainty
One would argue that today, much of the variance in pooled experiments is technical rather than biological. A printed tensor, run on standardized rails, exposes and stabilizes these sources of variation. This improves interpretability and increases the return on every additional experiment the company performs.

6. A platform that compounds in value
Once established, the tensor becomes a scaffold for continuous learning. Every new perturbation, cell type, or stress condition expands the map rather than creating another isolated dataset. This compounding structure is essential for a company trying to build general biological intelligence.

In short, the strategic value is not just in having a high-quality dataset. It is in establishing the company’s first biologically principled reference system. That system allows fragmented efforts to converge, allows models to learn the right abstractions, and gives the organization a mechanism for turning experiments into cumulative knowledge rather than isolated results.

Design Rationale

1. Cell Line Selection

We prioritize cell models that are:
Cas9-editable and compatible with pooled lentiviral delivery
Adherent and imageable, suitable for imaging analysis
Biologically diverse across lineage and stressor axes

Constraints for choice:
POSH is expensive so target 3 to 5. Optionality for more later, depending on budget and tensor asks. 
Must be Cas9 friendly.
Must be transducible at library scale.
Must be adherent so the cells sit still for POSH.
Must be imageable and segmentable.

These constraints eliminate most hematopoietic stuff and anything that rounds up or floats. So we stay in epithelial and fibroblast land, with one or two slightly weirder lines for biological range.

Group 1. Core Lines (Run in all experiments)

Cell Line
Rationale
A549
Lung epithelial. Very POSH friendly. Adherent. Segmentable. We have made and run A549-Cas9 lines many times. Good redox response. Good for mito dyes.
HepG2
Hepatic. Adherent. Good cytoplasm area so segmentation is clean. Used previously so Cas9, lentiviral transduction, Imaging and segmentability de-risked.
U2OS
Flatter. Big nuclei. Very easy to segment. Takes Cas9 well. Take libraries well. Imaging people like it, but not used extensively at insitro, yet.


These lines give us the stable, high-quality data needed to map the broad architecture of cellular response patterns to perturbation across human cells. They establish the baseline patterns of stress biology that hold across lineages and provide the training substrate for any foundation model built on top of the tensor. Their robustness also keeps the technical operation smooth, allowing us to surface and fix workflow issues early and reducing the biological noise that would come from more fragile or sensitive cell systems.


Group 2. Expansion Lines (Pick ~3 to reach 6?)

Cell Line
Rationale
LX-2
Hepatic stellate / fibrotic axis. Models ECM remodeling and TGFβ-driven signaling. Adherent but slower. Valuable for fibrosis and redox crosstalk.
iPSC-NGN2
Neuron-like cells generated from iPSCs. Strong mitochondrial and oxidative stress phenotypes, clean subcellular structure, and a distinct lineage program. Usable for POSH, though more sensitive to density and handling. Editing and transduction work, but are slower than in immortalized lines. High value for adding a neuronal axis without moving to specific sub-set e.g. hNIL.
…
…
TBD “favorite” line
Each therapeutic or platform group will have a preferred candidate here. Some will argue for an additional neuronal model, others for cardiometabolic or fibro-inflammatory contexts. These preferences reflect both local biology and local expertise. The actual requirement is simpler: we choose additional lines that are plausible candidates for adding new structure to the tensor, then let the data tell us whether they expand the biological space or simply echo what the core set already provides.



2. Choosing biological axes that give the tensor shape

We are not trying to cover every pathway. The goal is to anchor the dataset around biological systems that reliably produce structured, interpretable responses across cell types and stress contexts. To focus the effort, we prioritize pathways that meet three tests:

Pleiotropy
They show up across unrelated disease areas, not just one niche.

Connectivity
They occupy regulatory hubs where multiple signaling pathways integrate and produce coordinated downstream responses.

Actionability
They include components that are realistically tractable, meaning there is a plausible path to modulating their activity through small molecules, biologics, or genetic tools. Not every node needs to be druggable, but the pathway should contain intervention points that can be pushed experimentally and, in principle, therapeutically.

Six systems rise to the top as the most productive starting points for new data generation.
Mitochondrial dysfunction
ER stress and proteostasis
Lipid handling
Lysosomal and trafficking defects
Fibrotic / ECM remodeling
Oxidative response

3. Stressor panel: defining the biological rails
The stressor panel is one of the easiest components to design poorly. Without discipline, it either devolves into an arbitrary assortment of available compounds or expands into an overly complex pharmacological showcase. Neither approach serves the goals of a printed dataset.
The purpose of the stressor panel is to selectively engage each axis of the tensor. It is not intended to mimic specific diseases or reproduce every known form of cellular injury. Its role is to introduce controlled, interpretable variation that reveals the underlying biology of interest.
Each stressor is selected because it consistently activates one of the six defined stress-response systems across multiple lineages, performs reliably in pooled screening environments, and produces morphological signatures that we can resolve without requiring excessive modeling complexity.
Mitochondrial dysfunction
Rotenone or Antimycin A
These compounds consistently impair electron transport and induce robust, well-characterized mitochondrial phenotypes accompanied by clear redox signatures. Their extensive use in the literature indicates that they scale across diverse cell lines without introducing severe viability constraints, making them suitable for pooled profiling at experimental breadth.
ER stress and proteostasis
Tunicamycin or Thapsigargin
Tunicamycin induces the unfolded protein response by blocking N-linked glycosylation, creating a defined burden on ER folding capacity. Thapsigargin perturbs ER homeostasis through depletion of calcium stores, triggering a complementary but mechanistically distinct stress program. Together, these perturbations span the major entry points into ER stress signaling. Each should produce reproducible and well-resolved Cell Painting signatures that map cleanly onto ER triage pathways across multiple lineages
Lipid handling
Oleic acid or palmitate
These are canonical metabolic stressors that drive lipid accumulation, challenge fatty acid handling pathways, and amplify variation in lipid droplet formation and storage. Their effects are robust, well characterized, and scalable in pooled settings as evidenced by our use previously. Importantly, they reveal clear lineage-dependent differences, particularly between hepatic and epithelial systems, making them valuable for comparing regulatory architecture across cell types.
Lysosomal and trafficking defects
Bafilomycin A1
Bafilomycin A1 inhibits autophagosome–lysosome fusion by blocking vacuolar ATPase activity, creating a defined and interpretable disruption in autophagic flux. This perturbation should produce reliable, high-contrast cytoplasmic and organellar phenotypes that are readily captured by Cell Painting. Its effects are expected to be consistent across lineages, making it a dependable anchor for interrogating lysosomal and trafficking defects within the tensor.
Fibrotic and ECM remodeling
TGFβ1
TGFβ1 is a canonical inducer of fibroblast activation and a central regulator of ECM remodeling programs. In LX-2 cells it serves as a clear anchor for the fibrotic axis, producing well defined transcriptional and morphological transitions. In epithelial lines it reveals the extent to which cells can be driven toward a mesenchymal state, exposing lineage boundaries in response flexibility and stress tolerance.
Oxidative response
tert-butylhydroquinone or menadione
These compounds induce controlled oxidative stress with reproducible redox and cytoskeletal signatures, providing a reliable entry point into the oxidative response axis. The objective is not to drive extensive damage but to elicit structured, interpretable oxidative phenotypes that reveal how cells manage redox imbalance across lineages.

Across the six axes, we select one or two representative compounds per pathway depending on operational and financial constraints. The aim is not to build a pharmacological catalog but to establish a focused set of control inputs that allow the tensor to express its underlying biological structure.

4. Measurement plan: what the tensor actually records
The tensor becomes useful when the rails are measured consistently across lineages, stressors, and batches. Otherwise we are back where we started.
The measurement plan defines the observations that anchor the printed dataset. It has three primary layers.
Layer 1. Cell Painting for morphological archetypes
This is the backbone. Nuclei, actin, mitochondria, ER, membrane. A set of stains that gives us enough geometry to infer subcellular organization and compute high-dimensional embeddings.
The model does not need to know why a mitochondrion is swelling. It needs to know that it is swelling in cell type A and not in cell type B. That contrast is the currency.
Layer 2. POSH phenotypes from pooled perturbations
Each gRNA produces a morphological signature in stressed and unstressed contexts. These signatures become the perturbational fingerprints that define gene-level contributions to each axis.
The important part is contrast.
A gene that appears inert until the cell is pushed into ER distress is still informative.
A gene that produces a phenotype only in neurons but not epithelial cells is drawing the boundary of lineage dependence.
A gene that shifts lipid droplet morphology only under oleic acid is pointing to context-specific regulation.
Layer 3. Anchor metrics for basic biology
Basic viability. Mitochondrial health. Redox ratio. Simple scalar measurements that act as calibration points. None of these are glamorous, but they let you detect drift, floor effects, and assay collapse before they propagate into the embeddings.
Optional Layer 4. Transcriptomic overlays (FLEX Perturb-seq)
This layer is not required for printing the tensor, but once FLEX is ready, a subset of conditions can be run to add gene expression context. The point is not depth. The point is grounding the morphological manifold in transcriptional reality. 
5. Success Criteria and Evaluation Metrics
The tensor is only valuable if it produces a signal that generalizes beyond individual assays and informs program-level decisions. The evaluation framework must therefore demonstrate three things:
The dataset is technically stable.
The biology is structured, lineage-aware, and reproducible.
The outputs directly support TA-level reasoning and target discovery.
Below are the criteria we use to determine whether the tensor is succeeding.
1. Technical Reproducibility and Assay Stability
We expect the tensor to show high technical fidelity across replicates, batches, and days. Key metrics:
Embedding reproducibility
Cell-level embeddings from replicate plates should cluster tightly, with low within-condition variance.
Correlation between replicate morphological signatures should exceed predetermined thresholds (for example r > 0.85 for major axes of variation).


Stressor consistency
Each stressor should produce a stable, lineage-consistent morphological manifold across runs.
Dose-response curves should be monotonic and reproducible.


Perturbational fingerprint replicability
gRNA-level signatures for the same gene should correlate across replicates and across days.
Genes with known biology (positive controls) should recover expected phenotypes reliably.


These metrics answer the skeptics’ first question:
 “Is this just noise?”
2. Biological Structure and Informative Variation
The tensor must demonstrate that the biology is not only stable but meaningfully organized in a way that reflects real cellular pathways and lineage differences.
Separation of lineage and state
Embeddings should cleanly distinguish cell types in unstressed conditions.
Under stress, the tensor should expose shared pathways and lineage-specific responses in a measurable way.


Axis recovery
Stressors intended to activate mitochondrial, ER, oxidative, fibrotic, or lysosomal programs must produce separable, interpretable signatures.
Enrichment analyses should confirm that canonical markers and pathways load on the expected axes.


Concordance with external datasets
Genes with known roles in stress response should display expected perturbational patterns.
Signatures should align with Perturb-seq and Cell Painting results from other organizations or public datasets where relevant.


These metrics answer the TA concern:
 “Does this reflect real biology or just assay quirks?”
3. Program-Relevant Predictive Value
TA teams will ask:
 “How do I know this will help my program?”
We evaluate usefulness by demonstrating that the tensor produces insights that translate into TA-relevant hypotheses.
Context-specific regulators
The tensor should identify genes that regulate stress pathways only in certain lineages or under certain perturbations.
 This is precisely the kind of actionable specificity TA teams need.


Cross-cell predictions that hold
If a gene regulates oxidative resilience in hepatocytes in the tensor, this should predict similar behavior in disease models dependent on redox imbalance.


Pathway-level insights
Clustering of gene perturbations should recover known biological modules (e.g., UPR, mitophagy, TGFβ signaling) and identify new candidate nodes within them.


Target nomination value
For at least one TA-relevant axis (fibrosis, metabolic stress, neurodegeneration), the tensor should surface high-confidence regulators that motivate downstream validation.


These metrics directly address the TA objection:
 “Prove that this gives me hypotheses I wouldn’t have found otherwise.”
4. Integration With Existing and Future Screens
A printed dataset earns its keep when it becomes a reference atlas that future screens can attach to.
Cross-dataset alignment
New POSH or Perturb-seq runs should map onto the existing tensor with minimal retraining of embeddings.
Batch-normalization models should show that new experiments fall into existing structure rather than creating new coordinate systems.


Reduction in follow-up experimental load
The tensor should allow pathway-level inference without running large disease-specific screens each time.
TA teams should be able to ask:
 “Where does my gene sit on the stress axes?”
 “Is this phenotype lineage-specific or conserved?”
 And get a reliable answer from the atlas.


This addresses the operational concern:
 “Does this help us run fewer, better experiments?”
5. Clear Failure Modes and Stop Conditions
The tensor is successful only if we can tell when it is not.
We define fail conditions:
stressors fail to produce distinct manifolds
lineage differences collapse
perturbational fingerprints show low replicability
embeddings drift beyond tolerance across batches
variance explained by biological factors falls below a target threshold
positive control genes do not recover expected signatures
If these occur, the run is not printable, and TA teams should not be asked to interpret it.
In sum
Success is judged by whether the tensor:
increases certainty
reduces confounding
reveals structure
generates hypotheses that matter to programs
This section tells TA leaders, in plain terms:
We will know it works because the biology will organize itself, reproducibly, into something we can use. If it doesn’t, we don’t call it printed.
The printed tensor is not another screen. It is the reference frame the company has been missing. By grounding perturbations, stressors, and lineages in a shared experimental geometry, we replace a scattered collection of datasets with a coherent map of how human cells respond to challenge. That map becomes the substrate for models that learn biology rather than artifacts, and for programs that start with mechanism instead of guesswork.
The near-term value is clarity. We learn which pathways are conserved, which are lineage-bound, and which genes act only when the cell is pushed into the right corner of its state space. We expose where our assays are stable and where they drift. We give TAs a way to place their hypotheses on a set of axes that actually generalize.
The long-term value is compounding. Each new experiment attaches to the same coordinates, adding resolution rather than noise. The tensor becomes an atlas that unifies POSH, Cell Painting, and transcriptomic profiling into a single biological structure the whole company can build on.
If it works, the organization stops rebuilding its coordinate system from scratch every quarter. It starts learning on a shared substrate. And that is the beginning of general biological intelligence — not as an aspiration, but as infrastructure.

The push back section
The premise is simple. 
A lot of things can go wrong upstream:
Mutations
misfolded proteins
lipid overload
trafficking defects
oxidative shocks
inflammatory cues
environmental toxins
aging noise
The causes are messy and heterogeneous. The space of insults is enormous.
But the ways a cell actually fails are not infinite. As the system destabilizes, it drops into a small set of conserved breakdown modes.
Mitochondrial failure
ER collapse
Redox imbalance
Lipid overload
Trafficking congestion
Fibrotic remodeling
The inputs are sprawling. The outputs aren’t. They converge.
That is the core claim. Many roads lead into a disease, but cells only know a few ways to fall apart.
This is why the printed tensor matters. If these failure modes are real, conserved, and structurally simple, then measuring different cell types, stressors and perturbations on shared rails will reveal the underlying axes cleanly. If they’re not, the tensor collapses into noise.
But everything we know points the same way. Cell Painting factorizes into a few programs. Perturb-seq does too. Organelle biology has described the same bottlenecks for two decades. Different insults, same funnels. 
And that gives us something powerful:
you can map the failure modes
you can compare them across lineages
you can measure how genes shape them
you can build models that generalize beyond any single disease
you can predict where a new perturbation lands in the space
None of that works unless the rails are shared. Convergence only becomes visible when the measurement system itself is stable.
The scientific bet is simple and bold.
Disease etiology is high dimensional.
Cellular failure is low dimensional and discoverable.
But if everything converges, isn’t it already too late to intervene?
Convergence isn’t terminal. Cells shift into these programs long before they break.
UPR engagement
mitochondrial rewiring
lipid droplet reorganization
lysosomal backlog
ECM stiffening
These are adaptive states, not death throes. They’re how cells buy time. That’s the window where intervention makes sense.
The tensor isn’t about collapse. It’s about the structured trajectories into these modes.
Upstream chaos, downstream order. The insults vary. The responses don’t.
If twenty unrelated perturbations all drift toward “ER triage overload” or “redox depletion,” then those nodes become leverage points. You’re not waiting for the funnel to finish. You’re targeting the narrow passages everything upstream must move through.
You treat states, not causes. Most causes can’t be undone. Genetic variants, aging drift, environmental damage, none of these reverse cleanly.
But the state can be modulated.
e.g boost chaperone capacity
buffer redox collapse
increase autophagic flux
slow ECM stiffening
These work because the state space is small and conserved.
The tensor tells you which state matters in which lineage. Cells don’t compensate the same way.
Neurons fracture when redox buffering gives out.
Hepatocytes hold until lysosomal flux bottlenecks.
Fibroblasts run straight into TGFβ-driven stiffness.
Without a shared measurement grid, you can’t see those lineage-specific fault lines. With it, you can.
That’s therapeutic logic, not cartography.
The earliest shifts are the most structured
Long before apoptosis, subcellular organization tilts in stereotyped ways.
Cell Painting catches those tilts.
POSH tells you which genes push or prevent them.
Intervention lives exactly at that stage.
If intervention requires early detection, the tensor is the early detection.
You’re not using convergence to react late.
You’re using it to learn the geometry of early stress trajectories so you can steer them.
If the true causality, and the disease-specific uniqueness, sit upstream, why invest in a shared tensor at all? Why not focus our effort on mapping those upstream pathways directly instead of collapsing everything into shared failure modes?
Because upstream causality is real, but it’s not learnable at scale without a scaffold. The heterogeneity is too large. Twenty thousand genes, hundreds of pathways, thousands of context-specific interactions. If you try to map that space directly, you drown in degrees of freedom.
Downstream constraints are the structure that makes upstream causality interpretable.
Here’s the practical logic:
Upstream differences only make sense when anchored to shared dynamics
You can’t tell whether a gene is “unique to ALS” or “unique to hepatocytes” or “unique to oxidative stress” unless you understand the common axes the system always moves through. Without that anchor, every upstream effect looks unique, and none of them generalize.


The shared tensor gives you the coordinate system
 It’s the reference frame. Once you have the conserved stress axes, then you can ask:
 Which perturbations divert the trajectory?
 Which amplify it?
 Which bypass it altogether?
 That’s how you surface true upstream causality instead of noise.


Most upstream signals are weak and context-dependent
But their projection onto the conserved axes is stable.
That’s what lets you separate real mechanistic signals from idiosyncratic artifacts of a single assay, cell line, or lab condition.


Causality without structure isn’t useful
You can list pathways forever.
What matters is whether they explain movement along stable biological dimensions.


The tensor doesn’t replace upstream mapping.
It makes upstream mapping feasible.
Uniqueness emerges from deviation, not from cataloguing
If you know the shared dynamics, you can spot the exceptions — the places where a lineage or disease truly breaks the rules.
That’s where the real therapeutic gold is.


The upstream search becomes targeted instead of blind
You’re no longer asking “what changed?”
You’re asking “what changed relative to the expected trajectory?”


That’s a completely different level of interpretability.
… but
“In ALS, we didn’t start from generic stress programs. We found something disease specific, dysfunctional splicing through TDP43 and cryptic exon exposure. And the actionable targets weren’t the universal failure modes. They were the intermediate regulators that connect TDP43 loss to cell death. If we had focused on shared stress axes instead of upstream specifics, we might have missed exactly the layer that gave us druggable entry points for ALS.”





