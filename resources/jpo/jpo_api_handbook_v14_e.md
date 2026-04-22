This  English  version  of  Handbook  is  a  provisional  translation  of  the  original

Japanese version.

If there are any discrepancies between this provisional translation and the original,

the original shall prevail in all cases.

Patent Information

Retrieval APIs
Handbook

Ver. 1.4

Information Technology and Patent Information

Management Office, General Coordination Division,

Policy Planning and Coordination Department,

Japan Patent Office (JPO)

Revision History

Ver.1.4

Modified the descriptions of the following points changed in this

edition.
⚫  Modified the associated descriptions along with the

establishment of Patent Information Retrieval APIs Support

Center

⚫  Remove FAQs (incorporated into FAQ of API Information

Website

Add explanation of the following API added in this edition.
⚫  Design and trademark APIs
⚫  One Portal Dossier,API
⚫  Patent J-PlatPat Fixed Address API
⚫  Patent PCT National Phase Application Number API

Ver.1.3

Ver.1.2

Add explanation of the following point added in this edition
⚫  Access limit about users that provide patent information

Index

Article 1. Introduction .......................................................................................................... 1

Article 2. Information Provided by our APIs....................................................................... 1

(1)

(2)

Types of APIs .......................................................................................................... 1

The Scope of our Accumulated Information ......................................................... 4

(3)  Updates of our Accumulated Information ............................................................ 4

Article 3. Terms of Use ......................................................................................................... 4

(1)

Available Time ........................................................................................................ 4

(2)  User Registration ................................................................................................... 4

<Registration Procedures> ................................................................................................... 6

<Registration Forms to be Addressed to> .......................................................................... 7

(3)

(4)

Preparations for Users ........................................................................................... 8

Change of User Information .................................................................................. 9

Article 4. Privacy Policy ...................................................................................................... 10

Article 5．Inquiries ............................................................................................................ 10

<Office in Charge> ............................................................................................................... 11

Patent Information Retrieval API    User Registration Form（Corporate Users） ........... 12

Patent Information Retrieval API    User Registration Form（Individual Users） ............ 13

Authentication Procedures................................................................................................ 16

Article 1. Introduction

The Patent Information Retrieval APIs allow you to mechanically retrieve part
of  the  JPO’s  patent  information  provided  by  the  J-PlatPat,  patent  information
standardized data and IP5 offices’ (EPO, JPO, KIPO, CNIPA and USPTO) patent
dossier information provided by the One Portal Dossier (OPD). Using our APIs,
users can mechanically retrieve status information of patent, design, trademark
applications  and  status  information  of  IP5  offices’  applications  provided  by  the
OPD, and refer to and/or enter data through them when preparing documents to
be submitted to the Japan Patent Office (JPO).

We  hope  that  the  use  of  the  Patent  Information  Retrieval APIs  will  reduce
workload in handling patent information as well as increase opportunities to use
patent information.

Article 2. Information Provided by our APIs
(1)  Types of APIs

The Scope of information provided by the Patent Information Retrieval APIs
is  any  information  related  to patents,  designs,  trademarks  and  OPD  but not  to
utility models.

There are fourteen types of patent APIs available: one of them is to retrieve
status  information  in  JSON  format,  and  another  is  to  retrieve  procedural
documents in XML format(Patent) or HTM format(design and trademark), There
are eleven types of design and trademark APIs, and six types of OPD APIs (OPD-
API).  In  order  to  ensure  stable  operation  of  our  APIs  services,  the  APIs  are
configured with access limits. Outlines of available APIs and their daily access
limits are shown below in Tables 1 through 4. Please refer to the specifications of
the  Patent  Information  Retrieval APIs  and  of  the  XML Tag  Structures  for  more
details.

Table 1: Patent API Types and Daily Access Limits (no./day)

API types

Outlines

Access
limits
400

１

２

３

４

５

６

７

Patent Status Information

Retrieve  the  list  of  status  information  based  on
application nos.

Simplified Patent Status Information  Simplified  version  of  1

(without  priority

400

Patent

Application

Divisional
Information
Patent  Priority  Basic  Application
Information
Patent Applicants’ Names/Corporate
Names
Patent Applicants’ Codes

Patent Reference to Nos.

information and classification information)
Retrieve divisional application information based
on application nos.
Retrieve  priority  basic  application  information
based on application nos.
Retrieve  applicants’  names/corporate  names
based on applicants’ codes
Retrieve  applicant  codes  based  on  applicants’
names/corporate names
Retrieve  cross-reference
publication, and registration nos.

list  of  application,

30

30

200

200

50

Patent Application Documents

Mailed Patent Documents

８

９

for  Refusal

Notices  of  Reasons
(Patent)
Information  on  Cited  Documents
(Patent)
Registered Patent Information

10

11

12

13 Patent J-PlatPat Fixed Address

Retrieve  physical  files  of  patent  applications
based on application nos.
Retrieve  physical  files  of  patent  applications
based on application nos.
Retrieve notices of reasons for refusal based on
application nos.
Retrieve
reasons for refusal based on application nos.
Retrieve
application nos.
Retrieve J-PlatPat Fixed address

information  on  documents  citing

information  based  on

registered

Patent  PCT  National  Phase
Application Number

14

Retrieve national phase application number from
international application number or international
publication number

100

100

100

50

200

200

200

Table 2: Design API Types and Daily Limits (no./day)

API types

Outlines

Design Status Information

１

Retrieve  the  list  of  status  information  based  on
application nos.

Access
Limits
400

Simplified Design Status Information Simplified  version  of  1

(without  priority

400

２

3

4

5

6

7

8

9

10

Design Priority Basic Information

Design Applicants’ names/Corporate
names
Design Applicants’ Codes

Design Reference to Nos.

Design Application Documents

Mailed Design Documents

Notices  of  Reasons
(Design)
Registered Design Information

for  Refusal

11 Design J-PlatPat Fixed Address

information and original application information)
Retrieve  the  priority  basic  information  based  on

application nos.

list  of  application,

Retrieve  applicants’  names/corporate  names
based on applicants’ codes
Retrieve  applicant  codes  based  on  applicants’
names/corporate names
Retrieve  cross-reference
registration, and international registration nos.
Retrieve  physical  files  of  applications  based  on
application nos.
Retrieve  physical  files  of  applications  based  on
application nos.
Retrieve information on documents citing reasons
for refusal based on application nos.
Retrieve
application nos.
Retrieve J-PlatPat Fixed address

information  based  on

registered

Table 3: Trademark API Types and Daily Limits (no./day)

API types

Outlines

30

200

200

50

100

100

100

200

200

Access
Limits

Trademark Status Information

１

Simplified  Trademark
Information
Trademark Priority Basic Information Retrieve  the  priority  basic  information  based  on

Retrieve  the  list  of  status  information  based  on
application nos.
Simplified  version  of  1
information and original application information)

(without  priority

  Status

２

Trademark
names/Corporate names
Trademark Applicants’ codes

Applicants’

Trademark Reference Nos.

application nos.
Retrieve  applicants’  names/corporate  names
based on applicants’ codes
Retrieve  applicant  codes  based  on  applicants’
names/corporate names
Retrieve  cross-reference  list  of  application,  and
registration nos.

Trademark Application Documents  Retrieve  physical  files  of  applications  based  on

100

Mailed Trademark Documents

Notices  of  Reasons
(Trademark)
Registered Trademark Information  Retrieve

for  Refusal

application nos.
Retrieve  physical  files  of  applications  based  on
application nos.
Retrieve information on documents citing reasons
for refusal based on application nos.

registered

information  based  on

200

application nos.

11 Trademark J-PlatPat Fixed Address  Retrieve J-PlatPat Fixed address

200

400

400

30

200

200

50

100

100

3

4

5

6

7

8

9

10

Access
Limits
100

Table 4: OPD-API Types and Daily Limits (no./day)

API types

Outlines

OPD Family Information

OPD Family List Information

OPD Document List

OPD Citation and Classification

OPD Document Contents

OPD JP Document Contents

1

2

3

4

5

6

Retrieve patent family information based on IP5
offices’  application,  publication  or  registration
nos.（※1）
Retrieve patent family information based on IP5
offices’  application,  publication  or  registration
nos.（※2）
Retrieve  document  list  based  on  IP5  offices’
application nos.
Retrieve  citation  and  classification  list  based  on
IP5 offices’ application nos.
Retrieve  document  contents  based  on
offices’ application nos.
Retrieve JP document contents based on JPO’s
application nos.

IP5

300

300

100

100

100

  (※1) filing date, application nos, publication nos and registration nos
(※2) filing date, application nos, publication nos, registration nos, publication date and registration date

API types, file formats as well as access limits, however, may be altered in the

future.

(2)  The Scope of our Accumulated Information

The Patent Information Retrieval APIs provide you with the following scope of

information:

➢

➢

Information related to patent applications filed from July 2003 when JPO
started to accept electronic filings of international standards (XML format).
Information related to design and trademark applications filed from January
2001  when  JPO  extended  the  scope  of  electronic  filings  (the  actual
documents  that  have  been  received  or  created  after  January  2019  in
accordance with the scope of search possible by J-PlatPat).

*Even if you can retrieve some information related to applications filed before
the above-mentioned duration through some of the APIs, please note that such
information may be incomplete.

The scope of the information provided by IP5 offices except for JPO is decided

by each office's operation.

(3)  Updates of our Accumulated Information

Our accumulated information that our APIs refer to is updated every day. A
certain procedure at JPO on the day will be reflected to our accumulated data on
the next day in principle. For example, if a notice of reasons for refusal is issued
today, it will be so recorded in our accumulated data tomorrow, and so the APIs
will be able to retrieve the updated information from tomorrow.

The frequency of updates of the information provided by IP5 offices except for

JPO is decided by each office's operation.

Article 3. Terms of Use
(1)  Available Time

Patent Information Retrieval APIs are available 24 hours a day every day in

principle.

However,  you  may  not  be  able  to  use  them  temporarily  due  to  our  server
maintenance and the like. JPO will notify the users about server maintenances
and other unavailable occasions beforehand by email or on the API Information
Retrieval website.

(2)  User Registration

Those who wish to use the Patent Information Retrieval APIs are required to

register with us after giving consent to the Terms of Use. We accept
registrations of corporate and individual users who submit us their registration
forms 1 through 4 (Exhibit 1 through 4), respectively. We issue IDs and
passwords to the users who have completed registration procedures. As
stipulated in Item 1 of Article 3, users, both individual and corporate, are not
allowed to hold more than one ID; and users are not allowed to handover their

IDs to any third parties. Please note that there is a possibility that new
registrations would be closed when API users are exceeded predetermined
number. Especially, regarding OPD-API, we will inform you of the recruitment
status on the JPO website
（https://www.jpo.go.jp/e/system/laws/koho/internet/api-patent

info.html）.

Corporate bodies (as business corporations and patent attorney offices) are
the assumed main users of our APIs, and therefore the daily access limit of each
API  is  configured  so  as  to  meet  their  expected  demand.  On  the  other  hand,
depending  on  the  scale  of  business,  some  large  corporate  users  may  find  the
daily  access  limits  less  than enough.  Corporate users  wishing to use our APIs
more than their access limits with rational reasons may request increased daily
access limits up to the ceiling, or the double of their regular daily access limits.

However, we may be obliged to re-adjust such increased access limits in case

of problems caused on API operations due to excessive access.

Corporate  users  that  provide  patent  information  (hereinafter  referred  to  as
“Information Provider(s)”) may be allowed to increase their access to our APIs to
retrieve  physical  files  (8-10  of Table  1,  and  7-9  of Table  2  and  3)  to  five-times
more of the regular access limits if all of the conditions, A) through C), are met.
Information  Providers  may  consult  the  person  in  charge  at  JPO  (hereinafater
referred to as the “person in charge of Patent Information Retrieval APIs” together
with the person in charge of Patent Information Retrieval APIs Support Center)
about their access limits during registration procedures:

A)  To offer information provision services using their own database using JPO

patent information bulk data download services;

B)  to  add  patent  information  retrieval API  functions  to their  own  information
provision services as mentioned above and to avoid access concentration
to patent information retrieval API by a cache function, and

C)  To always comply with the Article 4 (1) of the Terms of Use (Provision of

Usage Information).

Please note that easing access limits of OPD-API (Table 4) is not accepted.

Corporate users may allow one or more of their staff to operate our APIs using
the only ID and password issued to them by JPO (More than one person of the
corporate users are allowed to access our APIs simultaneously using the same
ID and password).

On the other hand, individuals operating their own businesses and/or doing
research are the assumed API individual users. Special attention should be paid
to the fact that individuals already registered as individual users are not allowed
to  register  themselves  as  corporate  users  at  the  same  time.  In  case  such  an
individual  user  of  dual  registration  is  discovered,  not  only  such  individuals  but
also the corporate users that allowed such individuals to use their accounts may
be restricted of our API uses.

<Registration Procedures>

1．Filling out a Registration Form
Those who wish to register as users for APIs listed in Tables 1 through 3 are
requested to fill out either Registration Form 1 (Exhibit 1) or 2 (Exhibit 2). Those
who wish to register as users for OPD-API listed in Table 4 are requested to fill
out either Registration Form 3 (Exhibit 3) or 4 (Exhibit 4). Listed below are the
points we would like you to pay special attention to.

➢  Consent to the Terms of Use

Only those who give consent to the Terms of Use can be allowed to use our
APIs. After reading through the Terms of Use, please mark the checkbox to give
consent to them.

➢  Contact Information

Please write your contact email address and phone number. JPO will contact
you via email most of the time. You are required to inform JPO promptly of any
changes to your contact information.

In case we lose contact with you, your user registration may be cancelled in

accordance with Article 8 of the Terms of Use.

➢  Purposes of Uses

The purposes of uses of the Patent Information Retrieval APIs are listed in the
Article 6 of Terms of Use. Please describe your purposes of uses (in relation to
your businesses) as specific as possible. Even though your purposes of uses of
APIs go beyond what’s written on your registration form, you don’t have to apply
for such changes of purposes as far as you comply with the Terms of Use.

➢

IDs
JPO shall issue an ID and password to those who wish to use our APIs. We
may cater to your requests of your ID strings. Each ID, however, should satisfy
the following conditions:
(a)two or more out of the following three used:  ①numbers,  ②alphabets

(small letters only),  ③signs [’-‘ (hyphen), ‘_’ (underbar), and ‘.’ (dot)];

(b)8 to 15 digits in total; and

(c)no personal information included.

Please  clearly  differentiate  each  confusing  letters  and  symbols  such  as  ‘0’

(zero) and ‘O’ (‘O’ as in ‘Osaka’).

If the ID strings you request don’t satisfy all the above-mentioned conditions,
the person in charge of Patent Information Retrieval APIs may ask your opinion
before finally deciding your ID.

➢  Contact Persons (Corporate Users)

Please appoint someone whom the person in charge of Patent Information
Retrieval APIs can get in touch with all the time as your contact person(s). You

can register maximum of three contact persons in order to secure contact with us
at  all  times: You  can  register  one  email  address  and  phone  number  per  each
contact person.

Meanwhile, please register personal email addresses but not corporate email

addresses for general use nor mailing lists.

➢  Requests to Change Daily Access Limits (Corporate Users)

If  you  wish  to  change  the  daily  access  limits  of APIs,  please  write  the API
type(s) and rational reasons. For instance, filling 300 applications by your own
corporation or your attorney agents per year is generally recognized as a rational
reason. Also please refer to the identification numbers and types of APIs shown
in the Table 1 through 3 of (1) of Article 2 of this handbook (Please write ‘1’ for
‘status  information’  for  example).  You  can  request  maximum  of  three  types  of
APIs in principle.

If  you  are  an  Information  Provider  and  wish  to  change  your  access  limits,
please include the following information: your bulk data download service ID and
type(s) of your information provision services using our bulk download services.

2．Submission of Registration Forms

Those  of  who  wish  to  use  our APIs  should  register  with  us  by  sending  a
registration form either via email or postal mail to the person in charge of Patent
Information Retrieval APIs as follows.

<Registration Forms to be Addressed to>

Regarding APIs listed in Tables 1 through 3

Information  Technology  and  Patent  Information  Management  Office,  General
Coordination  Division,  Policy  Planning  and  Coordination  Department,  Japan
Patent Office

①  Email address: PA0630@jpo.go.jp
②  Postal address: 3-4-3 Kasumigaseki, Chiyoda-ku, Tokyo 100-8915, JAPAN

Regarding OPD-API listed in Table 4

International Information Technology Affairs Section, Information Technology and
Patent  Information  Management  Office,  General  Coordination  Division,  Policy
Planning and Coordination Department, Japan Patent Office

①  Email address: PA0I00@jpo.go.jp
②  Postal address: 3-4-3 Kasumigaseki, Chiyoda-ku, Tokyo 100-8915, JAPAN

You  may  need  a  photocopy  of  your  registration  form  as  your  identification
when  you  need  some  procedures  as  to  change  part  of  your  registration
information in the future. Therefore, please keep its photocopy with you.

3．Confirmation of Users’ IDs

The  person  in  charge  of  Patent  Information  Retrieval APIs  will  contact  the
person(s)  in  charge  of  corporate  users  and  individual  users  written  on  the
registration  forms  for  their  identifications  in  order  to  prevent  fraudulent  user
registrations.  Those  who  don’t  respond  to  the  person  in  charge  of  Patent
Information Retrieval APIs properly will not be registered as users.

4．Registration at JPO

Based  on  the  information  written  on  the  registration  forms,  the  person  in
charge of Patent Information Retrieval APIs will issue IDs and passwords to users.
We may need about a week before issuance of an ID and password.

After user registration procedures, the person in charge of Patent Information
Retrieval APIs will send IDs, passwords and available time of APIs to users via
email or the like.

(3) Preparations for Users

1．Systems

Patent  Information  Retrieval APIs  are  designed  to  be  utilized  by  linking  to
users’  systems. API  users  should  understand API  mechanisms,  authentication
method  with  ID  and  password,  characteristics  of  retrievable  data,  utilization  of
data in order to maximize our APIs.

Please refer to the specifications of APIs explained in the specifications of the
Patent  Information  Retrieval  APIs  and  of  XML  Tag  Structures.  The  person  in
charge of Patent Information Retrieval APIs will entertain questions regarding API
specifications  and  access  failures  but  not  programing  questions  from  users.
Useful information as usage and specifications of the Patent Information Retrieval
APIs is concentrated in our API Information Provision Website (URL: https://ip-
data.jpo.go.jp/pages/top e.html).

2．Usage Policies

Authentication procedure using ID and password is essential in order to use
our APIs. Users are expected to safekeep their IDs and passwords by themselves.
Even if some users carelessly leak their IDs and/or passwords to any third parties
and suffer loss due to fraudulent access by such third parties; JPO would never
accept any liability.

As explained above, each API is configured to a certain daily access limit. The
number  of  accesses  is  counted  when  you  receive  a  reply  in  response  to  your
access request to the API. The daily counting starts at 0:00 am by each ID. Even
though  you  haven’t  accessed  100%  of  daily  limits,  the  counting  is  reset  at

midnight  every  day.  API’s  reply  to  your  access  request  will  be  an  error  after
exceeding daily access limits.

At  corporate  users  more  than  one  staff  may  use  their  registered APIs. And
these staff can use the same set of ID and password issued to them by JPO to
log into our API system simultaneously. However, the daily access is counted by
each ID, and you won’t be able to use our APIs after exceeding the daily access
limits  until  the  next  day.  Please  coordinate  the  use  of  APIs  within  each
organization.

When there are excessive accesses concentrated on certain APIs in a short
period of time, an error is replied. Therefore, the users who access to APIs listed
in Tables 1 through 3, please adjust the total number of accesses per minute to
10 or less mechanically (or by program manipulation). The users who access to
OPD-API listed in Table 4, please adjust the total number of accesses per minute
to 5 or less. Please let the person in charge of Patent Information Retrieval APIs
know  if  you  can access  our APIs  during  nighttime  or  on  holidays  when there’s
smaller demand so as to disperse accesses.

In case the person in charge of Patent Information Retrieval APIs discovers
any suspicious behaviors in accessing our APIs, the staff will inquire such users
about their uses.

The users who have violated Article 8 of the Terms of Use shall be subject to

penalties as cancelation of their user registrations.

3．Authentications

Users should be authenticated using their IDs and passwords so as to obtain
access tokens before accessing to our APIs. Please refer to Exhibit 5 for further
details.

(4) Change of User Information

The  users  that  need  to  change  their  initial  user  information  after  they  start
using our APIs are advised to contact the person in charge of Patent Information
Retrieval APIs. Please inform the person in charge of Patent Information Retrieval
APIs  immediately  especially  when  you  change  your  contact  information  (email
address  and  phone  number).  Those  of  who  are  in  charge  of  corporate  users
created as a result of mergers and acquisitions are advised to contact the person
in charge of Patent Information Retrieval APIs immediately so as to change your
corporate information with us.

If  users  contact  the  person  in  charge  of  Patent  Information  Retrieval APIs
about the user information change, the person in charge of Patent Information
Retrieval APIs  will  confirm  their  identity  by  their  names,  phone  numbers,  and
email addresses. The person in charge of Patent Information Retrieval APIs may

request their identity confirmation documents (as a photocopy of the registration
form) if necessary.

Followings are important points for you to pay attention to when handling user

information:
➢  IDs and passwords

More than one set of ID and password shall not be granted to one user. When
users  request  to  change  their  IDs  and/or  passwords,  their  former  IDs  and/or
passwords will be deleted as soon as their new IDs and/or passwords are issued.
JPO shall not answer any questions regarding your former IDs and/or passwords.
When you decide to change your ID and/or password, or you have forgotten
your ID and/or password but wish to continue using our APIs without changing
them, please contact the person in charge of Patent Information Retrieval APIs
for advice. The person in charge of Patent Information Retrieval APIs may be able
to inform you with your ID and/or password again after confirming your identity.

➢  Users and Contact Persons

For  privacy  protection,  only  the  updated  information  about  individual  users
and contact persons of corporate users shall be registered. JPO shall not answer
any questions about former users and contact persons.

➢  Changes of Daily Access Limits

The users who hadn’t requested to increase the daily access limits upon user
registration  may  request  JPO  to  increase  the  daily  access  limits  in  the  future.
Please contact the person in charge of Patent Information Retrieval APIs referring
to the type(s) of API(s).

Article 4. Privacy Policy

Our API system automatically collects information related to APIs such as IP
addresses  of  users  and  API  types  they  used.  Users  (both  corporate  and
individual) are required to submit their individual information to JPO.

JPO will utilize such information submitted by users for smooth operation and
improvement  of  the  systems,  and  as  reference  information  for  planning  and
designing of future patent information policy. Except for such cases as when JPO
is requested for information disclosure based on laws and regulations, or there
are fraudulent accesses, assaults and other illegal activities and/or other special
circumstances;  JPO  shall  not  utilize  and/or  provide  any  of  the  information
collected to any third parties for purposes other than those stated above. However,
information  aggregated  and  processed  so  as  not  to  reveal  any  users’  private
information may be disclosed.
JPO  shall  take  necessary  measures  for  proper  maintenance  of  the  collected
information so as to avoid leakage, loss and/or damage of it.

Article 5．Inquiries

Users may make an inquiry to the following according to their needs regarding
our  API  uses.    Corporate  users  can  contact    through  their  contact  persons

registered at JPO. Depending on your inquiries we may need a few days before
responding  to  your  inquiries  from  Patent  Information  Retrieval  APIs  Support
Center, etc.

For  access  failure  inquiries,  please  describe  the  specifics  (especially  your

client used as API test tools, details of your requests or our responses).

<Office in Charge>

(1) General

Inquiry  (other

than  Application

for  User  Registration,  etc.

mentionedbelow (2))

Patent Information Retrieval APIs Support Center

Email address: contact@ip-data-support.jpo.go.jp

(2) Application for User Registration, etc.

Regarding APIs listed in Tables 1 through 3

Information  Research  and  Policy  Planning  Section,

Patent
Information
Technology  and  Patent  Information  Management  Office,  General  Coordination
Division, Policy Planning and Coordination Department, Japan Patent Office
Email address: PA0630@jpo.go.jp Phone number: 03-3581-1101 (ext. 2361)
Phone inquiries are accepted between 9:00am and 5:30pm when JPO is open.

Regarding OPD-API listed in Table 4

International Information Technology Affairs Section, Information Technology and
Patent  Information  Management  Office,  General  Coordination  Division,  Policy
Planning and Coordination Department, Japan Patent Office
Email address: PA0I00@jpo.go.jp Phone number: 03-3581-1101 (ext. 2505)
Phone inquiries are accepted between 9:00am and 5:30pm when JPO is open.

Patent Information Retrieval API    User Registration Form（Corporate Users）

Please refer to <Filling out a Registration Form> in (2) of Article 3 of the Patent Information Retrieval API Handbook.

Exhibit  1

Application Date

Consent to Terms of
Use

Corporate
Information

(month) (date), (year)

☐  Yes, I consent. *Please check the box for consent.

Address

Corporate name

Section/department

Job title

Person in charge１

Name

Email address

Phone number

Section/department

Person in charge２
(if any)

Job title

Name

Person in charge3
(if any)

Purposes of Uses

Desirable ID (if any)
*Required to meet
conditions (a), (b), and (c)

Increased daily
access limits

Email address

Phone number

Section/department

Job title

Name

Email address

Phone number

☐Yes ☐No *Please check one of them.
Rational reasons for access increase:
・
API nos. you wish to increase access limits:
・
*Please indicate 1) your ID for patent information bulk data download services and 2)
type(s) of information provision services if you are an Information Provider using the
above services.
・Your Patent Information Bulk Download Service ID:

・URL to your Information Provision Services:

Exhibit 2

Patent Information Retrieval API    User Registration Form（Individual Users）

Please refer to <Filling out a Registration Form> in (2) of Article 3 of the Patent Information Retrieval API Handbook.

(month) (date), (year)

☐  Yes, I consent. *Please check the box for consent.

Address

Name

Email address

Phone number

Application Date

Consent to Terms of
Use

User information

Purposes of Uses

Please  indicate  that  you  use  your  account  for  yourself  but  not  for  any  corporate

Confirmation

bodies.

☐  I confirmed the above. *Please check the box for confirmation.

Desirable ID (if any)
*Required to meet
conditions (a), (b), and (c)

Exhibit  3

OPD-API    User Registration Form（Corporate Users）

Please refer to <Filling out a Registration Form> in (2) of Article 3 of the Patent Information Retrieval API Handbook.

Application Date

Consent to Terms of
Use

Corporate
Information

(month) (date), (year)

☐  Yes, I consent. *Please check the box for consent.

Address

Corporate name

Section/department

Job title

Person in charge１

Name

Email address

Phone number

Section/department

Person in charge２
(if any)

Job title

Name

Email address

Phone number

Section/department

Job title

Name

Email address

Phone number

Person in charge3
(if any)

Purposes of Uses

Desirable ID (if any)
*Required to meet
conditions (a), (b), and (c)

Exhibit 4

OPD-API    User Registration Form（Individual Users）

Please refer to <Filling out a Registration Form> in (2) of Article 3 of the Patent Information Retrieval API Handbook.

(month) (date), (year)

☐  Yes, I consent. *Please check the box for consent.

Address

Name

Email address

Phone number

Application Date

Consent to Terms of
Use

User information

Purposes of Uses

Please  indicate  that  you  use  your  account  for  yourself  but  not  for  any  corporate

Confirmation

bodies.

☐  I confirmed the above. *Please check the box for confirmation.

Desirable ID (if any)
*Required to meet
conditions (a), (b), and (c)

Exhibit  5

Authentication Procedures

  Please follow the procedures below to use our APIs after receiving an access token and

also authentication using your ID and password.

（１）Receiving an Access Token

  Users are requested to visit the Token Generation URL given by JPO after registration in

order to receive an access token. http method in this case shall be as POST while Keys

and Values of http request Header and Body shall be specified as below.

Key

Value

Specified Location

Host

https://ip-data.jpo.go.jp

Content-Type

application/x-www-form-urlencoded

grant_type

password

username

ID issued by JPO

password

Password issued by JPO

Header

Header

Body

Body

Body

Please note that IDs and passwords should be encoded before transmission.

＜Sample of receiving an access token using curl command＞

curl -X POST -H "Content-Type: application/x-www-form-urlencoded" --data-
urlencode "grant_type=password" --data-urlencode "username=■■■" --data-
urlencode "password=▲▲▲（not encoded）" https://ip-data.jpo.go.jp/(Token
Acquisition Path)


