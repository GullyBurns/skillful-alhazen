# History: The Name Alhazen

## The Scholar

Ibn al-Haytham (965-1039 AD), latinized as **Alhazen**, was an Arab mathematician, astronomer, and physicist. He pioneered the scientific method through rigorous experimentation, five centuries before Renaissance scientists followed the same paradigm.

His masterwork, the *Book of Optics* (Kitab al-Manazir), fundamentally shaped understanding of vision, light, and perception. He was the first to correctly explain that vision occurs when light reflects from objects into the eye, overturning the ancient Greek "emission theory" that eyes emit rays.

But it's his philosophy of critical reading that inspires this project:

> *"The duty of the man who investigates the writings of scientists, if learning the truth is his goal, is to make himself an enemy of all that he reads, and, applying his mind to the core and margins of its content, attack it from every side. He should also suspect himself as he performs his critical examination of it, so that he may avoid falling into either prejudice or leniency."*

This approach remains radical: make yourself an *enemy* of what you read, attack it from every side, and suspect even yourself.

## The Nile Project Legend

According to historical accounts, Ibn al-Haytham's critical method emerged from extraordinary circumstances.

The Fatimid Caliph of Egypt, **al-Hakim bi-Amr Allah**, heard of Ibn al-Haytham's engineering reputation and invited him to regulate the annual flooding of the Nile River—a matter of crucial importance for Egyptian agriculture.

Ibn al-Haytham proposed building a dam south of Aswan. This was remarkably prescient—the modern Aswan High Dam stands in almost exactly the location he identified.

But when Ibn al-Haytham traveled south to survey the site, he realized the scheme was impractical with the technology available in his era. The engineering challenges were insurmountable.

He had to return to Cairo and inform the Caliph that his grand plan would fail.

This was dangerous. Al-Hakim was notoriously volatile and violent—he had executed scholars and officials for less. According to various historical sources, Ibn al-Haytham feigned madness to escape punishment.

He was placed under house arrest, where he remained for roughly ten years until al-Hakim's assassination in 1021.

During this confinement, Ibn al-Haytham produced his greatest works, including the *Book of Optics*.

**Sometimes the most productive work happens under constraint.**

## Project Origins

Skillful-Alhazen is forked from CZI's [alhazen](https://github.com/chanzuckerberg/alhazen) project, originally built at the Chan Zuckerberg Initiative to help researchers understand scientific literature at scale.

The original system used:
- LangChain for agent orchestration
- PostgreSQL for data storage
- Various LLM providers

This fork reimagines the architecture:
- **Claude Code** replaces LangChain (more capable, less complex)
- **TypeDB** replaces PostgreSQL (knowledge graph instead of relational DB)
- **Skills** replace notebooks (modular, reusable, documented)

The goal remains the same: AI-powered scientific knowledge engineering, embodying Alhazen's philosophy of critical engagement with sources.

## References

- [Wikipedia: Ibn al-Haytham](https://en.wikipedia.org/wiki/Ibn_al-Haytham)
- [Tbakhi & Amir 2007: Ibn Al-Haytham: Father of Modern Optics](https://pmc.ncbi.nlm.nih.gov/articles/PMC6074172/)
- [ibnalhaytham.com](https://www.ibnalhaytham.com/)
- [Britannica: Ibn al-Haytham](https://www.britannica.com/biography/Ibn-al-Haytham)
- [Original CZI Alhazen Repository](https://github.com/chanzuckerberg/alhazen)
