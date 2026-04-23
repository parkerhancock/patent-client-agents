# USPTO Searchable Indexes

Sourced from https://ppubs.uspto.gov/pubwebapp/static/pages/searchable-indexes.html (fetched automatically).

| Alias | Description | Format | Comment | USPAT | PGPUB | USOCR |
| --- | --- | --- | --- | --- | --- | --- |
| AACI | Applicant City | philadelphia.AACI. |  | Yes | Yes | Yes |
| AACO | Applicant Country | US.AACO. | Two letter country code | Yes | Yes | Yes |
| AAD | Applicant Data | philadelphia.AAD. | Composite field searches applicant name, city, state and country | Yes | Yes | Yes |
| AAGP | Applicant Group | research.AAGP. |  | Yes | Yes | Yes |
| AANM | Applicant Name | ge.AANM. |  | Yes | Yes | Yes |
| AAST | Applicant State | PA.AAST. | Two letter state code | Yes | Yes | Yes |
| AB | Abstract | method.AB. |  | Yes | Yes | No |
| ABEQ | Equivalent Abstract Text/Abstract | synthesis.ABEQ. | ABEQ returns same result as alias AB for FIT database. | Yes | No | No |
| ABFN | Abstract | synthesis.ABFN. | ABFN returns same result as alias AB for FIT, USPAT databases. | Yes | No | Yes |
| ABME | Abstract | synthesis.ABME. | ABME returns same result as alias AB for FIT and USPAT databases. | Yes | No | Yes |
| ABPR | Abstract | synthesis.ABPR. | ABPR returns same result as alias AB for FIT and USPAT databases. | Yes | No | Yes |
| ABTL | Abstract | synthesis.ABTL. | ABTL returns same result as alias AB for FIT and USPAT databases. | Yes | No | Yes |
| ABTX | Abstract | synthesis.ABTX. |  | Yes | Yes | Yes |
| AD | Application Filing Date | 20110111.AD. | (1) Four digit year, two digit month, two digit day (2) Only highlighted in KWIC (3) Can be range searched | Yes | Yes | No |
| AFD | Application Filing Date | "20161126".AFD. |  | Yes | No | Yes |
| AFFF | Affidavit 130 B Flag | yes.AFFF. |  | Yes | No | No |
| AFFT | Affidavit 130 B Text | "affidavit/declaration" $.AFFT. | Generally the text is "Patent file contains an affidavit/ declaration under 37 CFR 1.130(b)." | Yes | No | No |
| AP | Application Serial Number | 999900.AP. | Six digits with leading zeroes as necessary Can be range searched | Yes | Yes | No |
| APD | Application Filing Date | "19820802".APD. "20181207".APD. |  | Yes | Yes | Yes |
| APN | Application Serial Number | 321145.APN. | This matches the last six numbers of the application number. APN returns same results as aliases ARD or AP in USPAT databases. | Yes | Yes | Yes |
| APNR | Application Series Code and Serial Number with no slash | "15375290".APNR. "15375362".APNR. 153753$2.APNR. | (1) 2006 and newer (2) Two digit series code and six digit application number. Use "29" for design application series code (3) Can be range searched | Yes | Yes | Yes |
| APP | Application Series Code and Serial Number | 10/023235.APP. 13/965626.APP. 16/444401.APP. | Two digit series code for utility applications, "D" for design applications series code, forward slash, and six digit application number | Yes | Yes | Yes |
| APSN | Application Series And Number | "14759139".APSN. | This matches the Series (XX) and the six numbers of the application number in XX/YYYYYY. | No | Yes | No |
| ARD | Application Serial Number | "759139".ARD. | This matches the last six numbers of the application number in the patent. ARD returns same results as aliases AP or APN in USPAT databases. | Yes | No | No |
| ARP | Application Serial Number | "10759138".ARP. "965626".ARP. | Searches application Reference Group | Yes | Yes | Yes |
| ART | Art Unit | 2811.ART. | Three digits from 1971 to 2001, four digits from 2002 forward | Yes | No | Yes |
| AS | Assignee Name | Goodyear.AS. | (1) Derived field in JPO DBs. | Yes | Yes | No |
| ASCC | Assignee Country | JP.ASCC. | Searches Assignee Country | Yes | Yes | No |
| ASCI | Assignee City | "New York".ASCI. |  | Yes | Yes | Yes |
| ASCO | Assignee Country | DE.ASCO. | Two character country code | Yes | Yes | Yes |
| ASGP | Assignee Group | (School SAME medicine).ASGP. | (1) Provides logical grouping of: AS, ASCI, ASCO, ASST, ASTC, ASTX, ASZP (2) Only highlighted in KWIC | Yes | Yes | Yes |
| ASN | Applicant Name | Toyoda.ASN. |  | Yes | Yes | No |
| ASNM | Assignee Name | Electric.ASNM. | Searches Assignee Name/Assignee Organization Name - ASNM(1) | Yes | Yes | Yes |
| ASNP | Assignee Name | Joseph.ASNP. | Searches Assignee Name - ASNP(1) | No | Yes | No |
| ASPC | Assignee Postal Code | "22309".ASPC. | Searches Assignee Postal Code - ASPC (1) | No | Yes | No |
| ASSA | Assignee Address | main.ASSA. |  | No | Yes | No |
| ASST | Assignee State | NV.ASST. | Two letter state code | Yes | Yes | Yes |
| ASTC | Assignee Type Code | "02".ASTC. | Use quotes | Yes | Yes | Yes |
| ASTX | Assignee Descriptive Text | University.ASTX. | Only highlighted in KWIC | Yes | No | Yes |
| ASZP | Assignee Zip Code | 10504.ASZP. |  | Yes | Yes | Yes |
| AT | Kind Code Search and Application Type | A.AT. AND glitter A1.AT. AND glitter | Searches Application Type - APT (1) in USOCR and Publication Kind Code - KD (1): in USPAT | Yes | Yes | Yes |
| ATT | Attorney /Agent/Firm | Fox.ATT. |  | Yes | No | No |
| ATTY | Attorney Name | Fish.ATTY. | Searches Attorney Name - ATTY | Yes | No | Yes |
| AU | Examiner Group | 2128.AU. | Searches for patents in specific Art Unit (AU). | Yes | No | Yes |
| AY | Application Filing Year |  | (1) Four digit year (2) Can be range searched | Yes | Yes | No |
| BGTL | Brief Summary | sucrose.BGTL. |  | Yes | Yes | Yes |
| BGTX | Brief Summary | sucrose.BGTX. |  | Yes | Yes | Yes |
| BI | Basic Index | Cat.BI. | (1) 2005 and older provides logical grouping of: BSUM, DETD, DRWD, TI, AB, CLM (2) 2006 and newer provides logical grouping of: BSUM, DETD, TI, AB, CLM | Yes | Yes | Yes |
| BIC | Invention Title, Claims | heliport.BIC. | Searches in Abstract Paragraph - ABTX & Claims Text - CLTX And Title (TTL alias) | No | Yes | No |
| BIS | Description, Brief Summary | (fertilizer with legume).BIS. | Searches in Summary of Invention Paragraph - BSTX & Detail Description Paragraph - DETX | No | Yes | No |
| BLNM | Botanic Latin Name | rosa.BLNM. |  | No | Yes | No |
| BOTN | US Botanic Latin Name | Rhododendron .BOTN. | Searches Botanic Latin Name - BLNM | No | Yes | No |
| BSEQ | Brief Summary | wingspan.BSEQ. | Searches background /summary | Yes | No | Yes |
| BSFN | Brief Summary | batman.BSFN. | Searches background /summary | Yes | No | Yes |
| BSPR | Brief Summary | boa.BSPR. | Searches background /summary | Yes | No | Yes |
| BSTL | Brief Summary | google.BSTL. | Searches background/ summary | Yes | No | Yes |
| BSTX | Brief Summary | skipit.BSTX. | Searches background/ summary | Yes | Yes | Yes |
| BSUM | Brief Summary | Dog.BSUM. |  | Yes | Yes | Yes |
| BTNC | Botanical Name | Rose.BTNC. | 2006 and newer | Yes | No | Yes |
| BVRF | Botanic Variety | POULFELD.BVRF. |  | No | Yes | No |
| CC | Patent Family Country Search | US.CC. | Searches Country Code (in USPGPUB database) or Patent Family Country (in DERWENT database) | No | Yes | No |
| CCCC | Current CPC Combination Set Classification | ("1" ADJ2 A61K) .CCCC. (A61K SAME (L ADJ I)).CCCC. | Searches all Data for a single CPC Combination Set classification. | Yes | Yes | Yes |
| CCCO | CPC Combination Classification Original | C08G18/10.CCCO. | Searches CPC Original Classification Group | Yes | Yes | Yes |
| CCLS | Current US Classification | 14/4.CCLS. |  | Yes | Yes | Yes |
| CCOR | Current US Original Classification | 703/1.CCOR. | Searches USPC Original Classification | Yes | Yes | Yes |
| CCPR | Current US Classification, US Primary Classification | 703/1.CCPR. 703.CCPR. | Searches Current US Classification, US Primary Class/Subclass - CCPR | No | Yes | No |
| CCSR | Current US Classification, US Secondary Classification | 703/1.CCSR. 703.CCSR. | Searches Current US Classification, US Secondary Class/Subclass - CCSR | No | Yes | No |
| CCXR | Current US Cross Reference Classification | 52/155.CCXR. | Searches Current US Cross Reference Classification - CCXR | Yes | Yes | Yes |
| CHNL | Drawing Description | illustra$5.CHNL. | Searches under COUNT OF LINKED RING INDEX NUMBERS, DRAWING DESCRIPTION section | Yes | Yes | Yes |
| CICL | Current IPC Class | H04N.CICL. H04L.CICL. | 2006 and newer IPC Also searches Locarno Classification | Yes | Yes | Yes |
| CIOR | Issued US Original Class | 428/702.CIOR. |  | Yes | Yes | Yes |
| CIPC | International Classification | G06F17/$.CIPC. |  | Yes | Yes | Yes |
| CIPG | Current International Patent Classification Group | A61F2/00.CIPG. | IPC Reform: "Advanced" (A) and "Core" (C) levels. Displays in KWIC . | Yes | Yes | Yes |
| CIPN | Current International Patent Classification Non-Invention | G06F17/??.CIPN. | 2006 and newer | Yes | Yes | Yes |
| CIPP | Current International Patent Classification Primary | G06F17/??.CIPP. | 2006 and newer | Yes | Yes | Yes |
| CIPR | Issued US Original Classification | 703/1.CIPR. | US Class Issued for PGPUB | No | Yes | No |
| CIPS | Current International Patent Classification Secondary | G06F17/??.CIPS. | 2006 and newer | Yes | Yes | Yes |
| CISR | Issued US Cross Reference Classification | 345/419.CISR. | Searches US Class Issued/ National Further Classification | No | Yes | No |
| CIXR | Issued US Cross Reference Classification | 428/413.CIXR. |  | Yes | Yes | Yes |
| CLAS | Current US Class | "428".CLAS. | Use quotes | Yes | Yes | Yes |
| CLEQ | Claims | (method with bound$4).CLEQ. | Searches Claims Paragraph Equation - CLEQ | Yes | Yes | Yes |
| CLFN | Claims | contain.CLFN. Or system.CLFN. | Searches Claims Paragraph Footnote - CLFN | Yes | Yes | Yes |
| CLM | Claims | (Dog SAME Cat). CLM. | Use "S" kind code (S.KD.) when searching design patent claims | Yes | Yes | Yes |
| CLOA | CPC Original Additional Class | H05K.CLOA. | Searches CPC Original additional class - CLOA. This field only shows when KWIC is on. | Yes | Yes | Yes |
| CLOI | CPC Original Inventive Class | G06F.CLOI. | Searches CPC ORIGINAL CLASSIFICATION GROUP | Yes | Yes | Yes |
| CLPR | Claims | (lamina$4).CLPR. | Searches claims. | Yes | No | Yes |
| CLSP | Current US Classification, US Primary Class | "703".CLSP. and (composite same width) | (1) Current US Classification, US Primary Class - CLSP (2) Use quotes | No | Yes | No |
| CLSS | Current US Classification, US Secondary Class | "264".CLSS. and (conventional adj static adj pressing) | (1) Current US Classification, US Secondary Class (2) Use quotes | No | Yes | No |
| CLST | Claim Statement | claims.CLST. |  | Yes | Yes | Yes |
| CLTL | Claims | ((releas$4 carrier backing film)).CLTL. |  | Yes | Yes | Yes |
| CLTX | Claims | ((releas$4 carrier backing film)).CLTX. |  | Yes | Yes | Yes |
| COFC | Certification Of Correction Flag | yes.COFC. |  | Yes | No | Yes |
| COND | Continuity Data | CONTINUATION. COND. | 2006 and newer | Yes | Yes | Yes |
| COR | Current US Original Classification | 424/9.1.COR. |  | Yes | Yes | Yes |
| CORR | Correspondence Name and Street Address | Fox.CORR. |  | No | Yes | No |
| CPA | Continued Prosecution Application | CPA.CPA. prosecution.CPA. | 2006 and newer | Yes | Yes | Yes |
| CPC | Current CPC Classification | C12N7/00.CPC. C07C51/43-64. CPC. | (1) Exclude leading zeros (2) Searches CPCI, CPCA, and CPCT. (3) Range searching at the subgroup level. | Yes | Yes | Yes |
| CPCA | Current CPC Additional | A61K2039/5252. CPCA. | Exclude leading zeros | Yes | Yes | Yes |
| CPCC | Current CPC Combination Set | ("1" ADJ C07C51/43).CPCC. (C08G18/12 SAME C08G18/3228). CPCC. | Searches the ranks and CPC classifications of a CPC Combination Set. | Yes | Yes | Yes |
| CPCG | Current CPC Classification Group | (C07C51/43 ADJ2 F).CPCG. | Contains all data for a single CPC classification. | Yes | Yes | Yes |
| CPCI | Current CPC Inventive | C12N7/00.CPCI. | Exclude leading zeros | Yes | Yes | Yes |
| CPCL | Current CPC Subclass | C12N.CPCL. |  | Yes | Yes | Yes |
| CPCT | Current CPC Combination Set Tally | C07C51/43.CPCT. | Searches a single CPC classification in a CPC Combination Set. | Yes | Yes | Yes |
| CPLA | Current CPC Subclass Additional | C07C.CPLA. |  | Yes | Yes | Yes |
| CPLI | Current CPC Subclass Inventive | C07C.CPLI. |  | Yes | Yes | Yes |
| CPOA | CPC Original Additional Classification | B32B37/00.CPOA. |  | Yes | Yes | Yes |
| CPOG | CPC Original Classification Group | B32B37/00.CPOG. |  | Yes | Yes | Yes |
| CPOI | CPC Original Inventive Classification | B32B37/00.CPOI. |  | Yes | Yes | Yes |
| CRTX | Cross Reference To Related Applications | CONTINUATION. CRTX. | 2006 and newer | Yes | Yes | Yes |
| CXR | Current US Cross Reference Classification | 260/665R.CXR. |  | Yes | Yes | Yes |
| DBNM | Database Name | USPT.DBNM. PGPB.DBNM. USOC.DBNM. |  | Yes | Yes | Yes |
| DCD | Disclaimer Date | "20001018".DCD. | Search string format is YYYYMMDD. Returns same results as alias DD. | Yes | No | No |
| DCEQ | Claims | (chemical with (fluid liquid solvent)).DCEQ. | Alias DCEQ returns same results as alias CLM. Searches specifically Design Claims Paragraph Equations | Yes | No | Yes |
| DCFN | Claims | (chemical with (fluid liquid solvent)).DCFN. | Alias DCFN returns same results as alias CLM. Searches specifically Design Claims Paragraph Table | Yes | No | Yes |
| DCLM | Claims | (chemical with (fluid liquid solvent)).DCLM. | Alias DCLM returns same results as alias CLM. | Yes | No | Yes |
| DCPR | Claims | (chemical with (fluid liquid solvent)).DCPR. | Alias DCPR returns same results as alias CLM. | Yes | No | Yes |
| DCTL | Claims | (chemical with (fluid liquid solvent)).DCTL. | Alias DCTL returns same results as alias CLM. | Yes | No | Yes |
| DCTX | Claims | (chemical with (fluid liquid solvent)).DCTX. | Alias DCTX returns same results as alias CLM. | Yes | No | Yes |
| DD | Disclaimer Date | 20000630.DD. | Four digit year, two digit month, two digit day | Yes | No | Yes |
| DEEQ | Description | (polymer$4 same (HEAT$4 thermal$3 temperature)). DEEQ. |  | Yes | No | No |
| DEFN | Description | (polymer$4 same (HEAT$4 thermal$3 temperature)). DEFN. |  | Yes | No | No |
| DEPR | Description | (polymer$4 same (HEAT$4 thermal$3 temperature)). DEPR. |  | Yes | No | No |
| DETD | Detailed Description | smelting.DETD. |  | Yes | Yes | No |
| DETL | Description | (polymer$4 same (HEAT$4 thermal$3 temperature)). DETL. |  | Yes | No | No |
| DETX | Description | (polymer$4 same (HEAT$4 thermal$3 temperature)). DETX. |  | Yes | Yes | No |
| DID | Document Identifier | "US 3769742 A". DID. "US 20210180562 A1".DID. "US 6165768 A". DID. | Use hyphens between data elements or quotes around whole string | Yes | Yes | Yes |
| DRWD | Drawing Description | figure.DRWD. | Only 2005 and older | Yes | Yes | Yes |
| ECL | Exemplary Claim Number | "13".ECL. | Use quotes | Yes | No | Yes |
| EXA | Assistant Examiner | lee.EXA. |  | Yes | No | Yes |
| EXP | Primary Examiner | william.EXP. |  | Yes | Yes | Yes |
| FD | Application Date Search | 20120806.fd. |  | Yes | Yes | No |
| FIPC | Cited Foreign Reference IPC | G08G001/087.FIPC. | Only 2005 and older | Yes | No | Yes |
| FIRM | Legal Firm Name | (fish with richardson).FIRM. |  | Yes | No | Yes |
| FMID | Family ID | "24851933".FMID. "53057472".FMID. | Use quotes | Yes | Yes | Yes |
| FMIO | Family Identifier Original | "9981453".FMIO. |  | Yes | No | Yes |
| FRCC | Foreign Reference Country Code | AU.FRCC. |  | Yes | No | Yes |
| FRCL | Foreign Reference Citation US Classification | 123/6??.FRCL. | 2006 and newer | Yes | No | Yes |
| FRCO | Foreign Reference Country Code | AU.FRCO. |  | Yes | No | Yes |
| FRCP | Foreign Reference Citation CPC | B41C.FRCP. |  | Yes | No | Yes |
| FREF | Cited Foreign Reference Information | ET.FREF. | (1) 2005 and older provides Cited Foreign Reference IPC, country, US original classification, publication date, and patent number Returns data from across the Cited Foreign Reference paragraph (2) 2006 and newer provides Cited Foreign Reference US Classification, country, publication date, and patent number Returns data from across the Cited Foreign Reference paragraph | Yes | No | Yes |
| FRGP | Cited Foreign Reference Group | ("615" SAME SK). FRGP. | (1) Provides logical grouping of: Cited Foreign Reference country, publication date, and patent number (2) Using the SAME operator will return data for a specific cited foreign reference | Yes | No | Yes |
| FROR | Foreign Reference Citation Classification | 428/40.1.FROR. | USPC classification; Hits found within metadata (S); Hits found within metadata when KWIC is on (EAST) | Yes | No | Yes |
| FRPD | Cited Foreign Reference Publication Date | 20010100.FRPD. | Four digit year, two digit month, followed by two zeroes | Yes | No | Yes |
| FSC | Field of Search Class | "512".FSC. | Use quotes | Yes | No | Yes |
| FSCL | Field of Search CPC Main Class | B29C.FSCL. | CPC class only; Hits found within metadata (S); Hits found within metadata when KWIC is on (EAST) | Yes | No | Yes |
| FSCP | Field of Search CPC Classification | A47G.FSCP. | CPC class only; Hits found within metadata (S); Hits found within main text (EAST) | Yes | No | No |
| FSCS | Field of Search Class/Subclass | 43/90.FSCS. |  | Yes | No | Yes |
| FSI | Field of Search IPC | A01M.FSI. |  | Yes | No | Yes |
| FSIC | Field of Search IPC Main Class | G06F.FSIC. | 2006 and newer | Yes | No | Yes |
| FY | Application Year | 2010.FY. |  | Yes | Yes | No |
| GAU | Examiner Group | 2128.GAU. |  | Yes | No | No |
| GI | Government Interest | air.GI. |  | Yes | Yes | Yes |
| GOEQ | Government Interest | navy.GOEQ. | Most hits found within metadata (S) | Yes | No | Yes |
| GOFN | Government Interest | army.GOFN. |  | Yes | No | Yes |
| GOPR | Government Interest | (air adj force). GOPR. |  | Yes | No | Yes |
| GOTL | Government Interest | navy.GOTL. |  | Yes | No | Yes |
| GOTX | Government Interest | army.GOTX. |  | Yes | Yes | Yes |
| GOVH | Government Interest | (air adj force). GOVH. | Some hits found within metadata (S) | Yes | Yes | Yes |
| ICLS | Issued US Classification | 428/94.ICLS. | Provides logical grouping of: CIOR, CIXR | Yes | Yes | No |
| IN | Inventor Name | Doe.IN. |  | Yes | Yes | Yes |
| INAA | Inventor Authority Applicant | LR.INAA. | Legal Representative or Inventor (LR or INV) | No | Yes | No |
| INCC | Inventor Country Code | 1045.INCC. KR.INCC. Hailin.INCC. | Street address number (e.g. 1045 Sansome St); Hit found within metadata (S) | Yes | Yes | No |
| INCI | Inventor City | "New York".INCI. |  | Yes | Yes | Yes |
| INCO | Inventor Country | MO.INCO. | Two character country code | Yes | Yes | Yes |
| INCS | Inventor Citizenship | JP.INCS. | Two letter country code | No | Yes | No |
| INDC | Inventor Deceased | Smith.INDC. | Inventor name. | Yes |  | Yes |
| INGP | Inventor Group | (Doe SAME Visalia).INGP. (Gaston SAME Barcelona).INGP. | (1) Provides logical grouping of: Inventor name, city, country, street address, state, text, zip code (2) Using the SAME operator, data is returned for a specific inventor | Yes | Yes | Yes |
| INIF | Inventor Group | TT.INIF. | Any information under 'Inventor Information.' | No | Yes | No |
| INIR | Indicator Rule 47 | Y.INIR. | 2006 and newer | Yes | Yes | Yes |
| INNM | Applicant /Inventor Name | Ujima.INNM. | Applicant or Inventor Name. | Yes | Yes | Yes |
| INSA | Inventor Street Address | Oak.INSA. |  | Yes | Yes | Yes |
| INST | Inventor State | AK.INST. | Two letter state code | Yes | Yes | Yes |
| INTX | Inventor Descriptive Text | school.INTX. |  | Yes | No | Yes |
| INV | Inventor Name | Ujima.INV. | Inventor name. | Yes | Yes | Yes |
| INZP | Inventor Zip Code | 07945.INZP. | Use five digits | Yes | Yes | Yes |
| IOR | Issued US Original Classification | 210/600.IOR. | US classification. | Yes | Yes | No |
| IPC | Issued International Patent Classification | G06F30/10.IPC. | 2005 and earlier, zero padded | Yes | Yes | Yes |
| IPCC | Issued International Patent Classification Class | H04N.IPCC. | 2006 and newer | Yes | Yes | Yes |
| IPCE | Issued International Patent Classification Edition | "07".IPCE. | (1) 2005 and older IPC editions and Locarno editions, use quotes (2) 2006 and newer Locarno editions only, use quotes | Yes | Yes | Yes |
| IPCG | International Patent Classification Group | H04N.IPCG. | All IPCR information according to WIPO ST.8 Standard (post-2005) | Yes | Yes | Yes |
| IPCN | Issued International Patent Classification Non-Invention | H04N7???.IPCN. | 2006 and newer, no zero padding | Yes | Yes | Yes |
| IPCP | Issued International Patent Classification, Primary | H04N7???.IPCP. | 2006 and newer, no zero padding | Yes | Yes | Yes |
| IPCR | Current International Patent Classification, Primary and Secondary | G06F17/??.IPCR. | 2006 and newer, no zero padding | Yes | Yes | Yes |
| IPCS | Issued International Patent Classification, Secondary | H04N7???.IPCS. | 2006 and newer, no zero padding | Yes | Yes | Yes |
| IPCX | International Patent Classification, Secondary | B01D003/00.IPCX. |  | No | Yes | No |
| IXR | Issued US Cross Reference Classification | 210/600.IXR. | US classification. | Yes | Yes | No |
| KD | Document Kind Code | A1.KD. B1.KD. A.KD. Or I4.KD. | "A" for 2000 and earlier. B1 for patents without PGPUBs, B2 for patents with PGPUBs | Yes | Yes | Yes |
| LPAR | OCR Scanned Text | (jelly ADJ beans). LPAR. | Searches description text of the OCR DB | No | No | Yes |
| LRAG | Legal Representative Name | Susan.LRAG. | Applicant Representative. | Yes | No | Yes |
| LRCI | Legal Representative City | Alexandria.LRCI. | Applicant Representative's address (City). | Yes | No | Yes |
| LRFM | Legal Firm Name | Amen.LRFM. | Applicant representative's (AR) Firm Name. | Yes | No | Yes |
| LRFW | Principal Attorney Name | Ade.LRFW. | Applicant representative. | Yes | No | No |
| LRNM | Legal Representative Name | Susan.LRNM. | Applicant representative. | Yes | No | Yes |
| LRST | Legal Representative State | MD.LRST. | US state two letter code. | Yes | No | Yes |
| MSGR | Messenger Flag | MS.MSGR. | There are 5488 Messenger format documents | Yes | No | Yes |
| NCL | Number of Claims | "868".NCL. | (1) Use quotes (2) Can be range searched | Yes | No | Yes |
| NDR | Number of Drawing Sheets | "3273".NDR. | (1) Use quotes (2) Can be range searched | Yes | No | Yes |
| NFG | Number of Figures | "3654".NFG. | (1) Use quotes (2) Can be range searched | Yes | No | Yes |
| NPS | Number of Pages of Specification | "171".NPS. | Use quotes | Yes | No | Yes |
| OREF | Cited Other Reference Publication | annual.OREF. |  | Yes | No | Yes |
| ORPL | Other Reference Publication | WO.ORPL. | Two letter country code | Yes | No | Yes |
| PARN | Parent Case Information | 1997.PARN. | Can be used to search for patent numbers, application numbers, or other meaningful text | Yes | Yes | Yes |
| PATT | Principal Attorney Name | Ade.PATT. | Applicant representative. | Yes | No | Yes |
| PC | Patent Country, Document ID With Dashes | AU-20201001?? -A4.PC.US.PC. | Exemplary references. | No | Yes | No |
| PCAC | PCT Filing Document Country Code | US.PCAC. | Two letter country code. | No | Yes | No |
| PCAD | PCT Filing Date | 20161126.PCAD. | Four digit year, two digit month, two digit day. | No | Yes | No |
| PCAN | PCT Filing Number | PCT/US01/027?? .PCAN. | Exemplary references. | Yes | Yes | No |
| PCDV | PCT 371C124 Date | 20200609.PCDV. | Four digit year, two digit month, two digit day. | No | Yes | No |
| PCDW | PCT 102E Date | 20020104.PCDW. | Four digit year, two digit month, two digit day. | Yes | Yes | No |
| PCEQ | Continuity Data | REISSUE.PCEQ. | Type of continuation application. | Yes | No | Yes |
| PCFD | PCT Filing Date | 20010111.PCFD. | Four digit year, two digit month, two digit day. | Yes | Yes | Yes |
| PCFN | Continuity Data | REISSUE.PCFN. | Type of continuation application. | Yes | No | Yes |
| PCPD | PCT Publication Date | 20010111.PCPD. | Four digit year, two digit month, two digit day. | Yes | Yes | No |
| PCPN | PCT Publication Number | WO02/139??.PCPN. | Exemplary references. | Yes | Yes | No |
| PCPR | Continuity Data | REISSUE.PCPR. | Type of continuation application. | Yes | No | No |
| PCPT | PCT Or Regional Publishing Country | WO.PCPT. | Two letter country code. | Yes | No | Yes |
| PCT | PCT Filing Number | PCT/US01/027?? .PCT. | Exemplary references. | Yes | Yes | Yes |
| PCTL | Continuity Data | REISSUE.PCTL. | Type of continuation application. | Yes | No | Yes |
| PCTX | Cross Reference To Related Applications, Continuity Data | REISSUE.PCTX. | Type of continuation application. | Yes | No | Yes |
| PD | Patent Issue Date | 19971111.PD. 20210603.PD. | (1) Four digit year, two digit month, two digit day (2) Can be range searched | Yes | Yes | Yes |
| PGCD | Pre-Grant Publication Filing Type | CORRECTED .PGCD. | 2005 and older: NEW, ORIGINAL, AMENDED, CORRECTED, VOLUNTARY, REPUBLICATION. 2006 and newer: ORIGINAL, AMENDED, CORRECTED, VOLUNTARY, REPUBLICATION | No | Yes | No |
| PGCO | Pre-Grant Publication Country Code | US.PGCO. | Two letter country code. | No | Yes | No |
| PGKC | Application Kind Code | A9.PGKC. | Document Kind Code. | No | Yes | No |
| PGNR | Publication Reference Document Number | 2002003900$ .PGNR. | Exemplary application or publication numbers. | No | Yes | No |
| PGPY | Pre-Grant Publication Year | 2001.PGPY. | Four digit year. | No | Yes | No |
| PN | Patent Number | 6000000.PN. D475502.PN. PP12345.PN. RE38134.PN. T109201.PN. H002067.PN. 20080081638.PN. 3418855.pn. | (1) Seven digits for utility patents, "D" with six digits for design patents, "PP" with five digits for plant patents, "RE" with five digits for reissue patents, "T" with six digits in quote marks for defensive publications, and "H" with six digits for Statutory Invention Registration documents (2) Can be range searched | Yes | Yes | Yes |
| PPCC | Prior Published Document Country Code | US.PPCC. | Two letter country code. | Yes | Yes | Yes |
| PPKC | Prior Published Document Kind Code | A9.PPKC. | Document Kind Code. | Yes | Yes | Yes |
| PPNR | Prior Published Document Number | 20110070352.PPNR. 20190066203.PPNR. | published application number | Yes | Yes | Yes |
| PPPD | Prior Published Document Date | 20050310.PPPD. | 2006 and newer | Yes | Yes | Yes |
| PRAD | Priority Application Date | 20001111.PRAD. | Four digit year, two digit month, two digit day | Yes | Yes | Yes |
| PRAN | Priority Application Number | 999.PRAN. | Can be range searched | Yes | Yes | Yes |
| PRAY | Priority Application Year | 2002.PRAY. | (1) Four digit year (2) Can be range searched | Yes | Yes | Yes |
| PRC | Priority Application Country | FR.PRC. | Two letter code. | Yes | Yes | Yes |
| PRCC | Priority Claims Country | GB.PRCC. | country code | Yes | Yes | Yes |
| PRCO | Priority Application Country | JP.PRCO. | Two character country code | Yes | Yes | Yes |
| PRN | Priority Application Number | 999.PRN. |  | Yes | Yes | Yes |
| PRY | Priority Application Year | 2002.PRY. | Four digit year | Yes | Yes | Yes |
| PT1D | PCT 102(e) Date | 20020104.PT1D. | 2005 and older four digit year, two digit month, two digit day | Yes | No | Yes |
| PT3D | PCT 371 Date | 20020104.PT3D. | (1) Four digit year, two digit month, two digit day (2) Can be range searched | Yes | Yes | Yes |
| PTAC | PCT Application Country Code | NO.PTAC. | Two letter country code | No | Yes | No |
| PTAD | PCT Filing Date | 20010118.PTAD. | (1) Four digit year, two digit month, two digit day (2) Can be range searched | Yes | Yes | Yes |
| PTAN | PCT Application Number | PCT/US01/02758 .PTAN. |  | Yes | Yes | No |
| PTFD | PCT Filing Date | 20010221.PTFD. | year, month, date | Yes | No | Yes |
| PTPD | PCT Publication Date | 20020124.PTPD. | Four digit year, two digit month, two digit day | Yes | Yes | Yes |
| PTPN | PCT Publication Number | WO02/13965 .PTPN. |  | Yes | Yes | Yes |
| PY | Patent Issue Year | 2002.PY. 1999.PY. | (1) Four digit year (2) Can be range searched | Yes | Yes | Yes |
| R47X | Rule 47 Indicator | "4".R47X. | 2005 and older, use quotes | Yes | No | No |
| RAC | Reissue Appl Country | US.RAC. | shows in metadata, country code | Yes | No | Yes |
| RANR | Reissue Application Number | 11647498.RANR. | (1) 2006 and newer (2) Two digit series code and six digit application number with no slash (3) Can be range searched | Yes | No | Yes |
| READ | Reissue Application Filing Date | 19991006.READ. | Four digit year, two digit month, two digit day | Yes | No | No |
| REAN | Reissue Application Number | 810748.REAN. | Six digits | Yes | No | Yes |
| RECD | Reissue Patent Parent Status | "6321335" / "CON".RECD. | patent number | Yes | No | Yes |
| REEX | Reexamination Flag | "95/001320" / "reexam".REEX. | application number | Yes | No | Yes |
| REPD | Reissue Issue Date | 20010227.REPD. | Four digit year, two digit month, two digit day | Yes | No | Yes |
| REPN | Reissue Patent Number | 06192970.REPN. | Eight digits with leading zeroes as necessary | Yes | No | Yes |
| RFCO | Reference Cited Patent Country Code | DE.RFCO. | country code | No | Yes | No |
| RFIP | Cited Patent Literature International Patent Classification | "20040209299" / "C12Q1/68".RFIP. | patent number and classification | No | Yes | No |
| RFNR | Cited Patent Literature Reference Number | "6403319" / "0034".RFNR. | patent and paragraph number | No | Yes | No |
| RFPN | Reference Cited Patent Number | "6403319" / "001".RFPN. | patent and paragraph number | No | Yes | No |
| RFRS | Reference Cited Patent Relevant Passage | "6403319" / "0034".RFRS. | patent and paragraph number | No | Yes | No |
| RLAC | Continuity Related Application Country Code | DE.RLAC. | Two letter country code | No | Yes | No |
| RLAD | Related Application Filing Date | 20020108.RLAD. | (1) Four digit year, two digit month, two digit day (2) Can be range searched | Yes | Yes | Yes |
| RLAN | Related Application Number | 060048.RLAN. 17240097.RLAN. | (1) Six digits with leading zeroes as necessary (2) Can be range searched | Yes | Yes | Yes |
| RLCD | Related Application Parent Status Code | "6321335" / "CON".RLCD. | patent number and continuation status | Yes | No | Yes |
| RLCM | Related Application Child Patent Name | "6321335" / "CON".RLCM. | patent number and status | Yes | No | Yes |
| RLCN | Related Application Child Patent Number | "6321335" / "CON".RLCN. | patent number and status | Yes | No | Yes |
| RLCO | Prior Published Document Country Code | US.RLCO. | Two letter country code | No | Yes | No |
| RLFD | Related Application Filing Date | 20040107.RLFD. | Four digit year, two digit month, two digit day | Yes | Yes | Yes |
| RLGK | Related Application Parent Grant Patent Kind | "6321335" / "A1".RLGK. | patent number and kind | Yes | No | Yes |
| RLGM | Related Application Parent Grant Patent Name | "6321335" / "US".RLGM. | patent number granted country code | Yes | No | Yes |
| RLGY | Parent Grant Document Country | "6321335" / "US".RLGY. | patent number granted country code | Yes | No | No |
| RLHD | Related Application Child Patent Date | "6321335" / "1998".RLHD. | patent number and year | Yes | No | Yes |
| RLKC | Continuity Related Application Kind Code | A1.RLKC. |  | No | Yes | No |
| RLKD | Prior Published Document Kind Code | A1.RLKD. |  | No | Yes | No |
| RLPC | Related Application Parent Status Code | "62321335" / "CON".RLPC. "62321335" / "71".RLPC. 62321335/ "granted".RLPC. | patent number and status | Yes | Yes | Yes |
| RLPD | Related Application Patent Issue Date | 20020122.RLPD. | Four digit year, two digit month, two digit day | Yes | Yes | Yes |
| RLPK | Related Application Parent Patent Kind | "62321335" / "A1".RLPK. "62321335" / "A".RLPK. | patent number and kind | Yes | No | Yes |
| RLPM | Related Application Parent Patent Name | "6321335" / "CON".RLPM. | patent number and status | Yes | No | Yes |
| RLPN | Related Application Patent Number | 6341243.RLPN. 10997463.RLPN. | (1) Seven digit patent number (2) Can be range searched | Yes | Yes | Yes |
| RLPP | Related Application Parent PCT Document | "13751560" / "pct".RLPP. | application number | Yes | No | Yes |
| RLPY | Parent Document Country | "13751560" / "US".RLPY. | application number | Yes | No | No |
| RLRP | Related Application Related Publication | "13751560" / "pub".RLRP. | application number | Yes | No | Yes |
| RLTC | Related Application Type Of Correction | "13751560" / "cert.correct." .RLTC. | application number | Yes | No | Yes |
| RPAF | Reissued Patent Application Filing Date | 20011120.RPAF. | year, month, date | Yes | No | Yes |
| RPAK | Reissued Patent Application Kind | "11973896" / "E".RPAK. | application number | Yes | No | Yes |
| RPAN | Reissue Application Number | 10118207.RPAN. | (1) Two digit series code and six digit application number with no slash (2) Can be range searched | Yes | No | Yes |
| RPGP | Reissue Patent Group | 11973896.RPGP. | application number | Yes | No | Yes |
| RPID | Reissue Parent Issue Date | 20011120.RPID. | year, month, date | Yes | No | Yes |
| RPKD | Reissue Parent Kind | "11973896" / "E".RPKD. | application number | Yes | No | Yes |
| RPNR | Reissue Patent Number | 06914531.RPNR. | (1) Eight digit patent number with leading zero (2) Can be range searched | Yes | No | Yes |
| RPPC | Reissue Parent Publication Country | US.RPPC. and (drill with rotation) | (1) Searches Reissue Parent Publication Country - RPPC (2) Use quotes | Yes | No | Yes |
| SITX | Statutory Invention Text | "term".SITX. | statutory term | Yes | No | Yes |
| SIZE | Document Byte Size | 2589.SIZE. 73984.SIZE @size<2589 | number | Yes | Yes | Yes |
| SPEC | Description | ddPCR.SPEC. | text search | Yes | Yes | No |
| SQNB | Sequence CWU | "1".SQNB. |  | Yes | Yes | Yes |
| SQOC | Sequences List Text | "20080318802" / "sequence listing".SQOC. | PGPub number | No | Yes | No |
| SQOD | Sequences List Text | "20080318802" / "sequence listing".SQOD. | PGPub number | No | Yes | No |
| SQOI | Sequences List Text | "20080318802" / "sequence listing".SQOI. | PGPub number | No | Yes | No |
| SQTB | Sequences List Text | "20080318802" / "sequence listing".SQTB. | PGPub number | No | Yes | No |
| SQTL | Sequences List Text | "20080318802" / "sequence listing".SQTL. | PGPub number | No | Yes | No |
| SQTX | Sequences List Text | "20080318802" / "sequence listing".SQTX. | PGPub number | No | Yes | No |
| SRC | Application Series Code | "09".SRC. | Use quotes, two digits for utility applications, "D" for design applications | Yes | Yes | Yes |
| TI | Title | (Cat ADJ Dog).TI. | Use any non-stop word | Yes | Yes | Yes |
| TRM | Term of Patent | "14".TRM. | (1) For design patents (2) Use quotes | Yes | No | Yes |
| TRX | Term of Grant Extension | "100".TRX. | (1) width="25%"2006 and newer (2) Number of days term is extended (3) Can be range searched | Yes | No | Yes |
| TTL | Invention Title | molecular.TTL. | text search query | Yes | Yes | Yes |
| UNIT | Examiner Group | 1637.UNIT. | art unit number | Yes | No | No |
| URCL | US Reference Classification | 123/6??.URCL. | 2006 and newer | Yes | No | Yes |
| UREF | Cited US Reference Information | Doe.UREF. | (1) 2005 and older provides US Reference name, US original classification, patent date, patent number, US unofficial classification, US cross-reference classification Returns data from across the Cited US Reference Information paragraph (2) 2006 and newer provides US Reference name, US original classification, patent date, patent number and US classification (3) Returns data from across the Cited US Reference Information paragraph | Yes | No | Yes |
| URGP | Cited US Reference Group | (D167929 SAME Doe).URGP. | (1) Provides logical grouping of: Cited US Reference name, patent date, patent number (2) Using the SAME operator, data is returned for a specific patent | Yes | No | Yes |
| URNM | US Reference Name | Kihara.URNM. | Searches patentee name of a US cited reference | Yes | No | Yes |
| UROR | US Reference Classification | 536/22.UROR. | US class, subclass | Yes | No | Yes |
| URPD | US Reference Publication Date | 20050500.URPD. | (1) Four digit year, two digit month, two digit day (2) Can be range searched | Yes | No | Yes |
| URPN | US Reference Patent Number | 7029333.URPN. | US pat number | Yes | No | Yes |
| URUX | US Reference Classification | 536/22.URUX. | US class, subclass | Yes | No | Yes |
| URXR | US Reference Classification | 536/22.URXR. | US class, subclass | Yes | No | Yes |
| WKU | Publication Number | WO000209512A1 .WKU. "03466392".WKU. |  | Yes | No | Yes |
| XA | Examiner, Assistant | Smith.XA. |  | Yes | No | Yes |
| XP | Examiner, Primary | Smith.XP. |  | Yes | No | Yes |
| XPA | Examiner, Primary /Assistant | Louis-Jaques.XPA. | Searches first name of primary/assistant examiner | Yes | Yes | Yes |