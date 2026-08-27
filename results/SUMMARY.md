# Luxor vs AntPool live Stratum comparison

- Verdict: **INCONCLUSIVE: one or both endpoints supplied no observable jobs.**
- Duration: 426.929 seconds
- Luxor jobs: 0
- AntPool jobs: 15
- Paired comparisons: 0
- Mean weighted similarity: None
- Median weighted similarity: None
- Similarity range: None to None
- Identical branch-list pairs: 0

The score uses 0xB10C's published weighting, where later Merkle branches carry more weight.
This verdict applies only to the tested endpoints and observation window.

## Diagnostics

~~~json
{
  "luxor": {
    "responses": [],
    "errors": [
      "gaierror: [Errno -2] Name or service not known"
    ]
  },
  "antpool": {
    "responses": [
      {
        "error": null,
        "id": 1,
        "result": [
          [
            [
              "mining.notify",
              "000013a91"
            ],
            [
              "mining.set_difficulty",
              "000013a92"
            ]
          ],
          "000013a9",
          8
        ]
      },
      {
        "error": null,
        "id": 2,
        "result": true
      },
      {
        "id": null,
        "method": "mining.set_difficulty",
        "params": [
          65536
        ]
      },
      {
        "id": null,
        "method": "mining.set_difficulty",
        "params": [
          16384
        ]
      }
    ],
    "errors": []
  }
}
~~~
