# MUD Aggregator

This repository contains the MUD Aggregator, a Home Assistant integration capable of merging together a set of MUD snippets to generate a consolidated gateway-level MUD file.
The snippets should be provided by plug-in developers and have to be written in a MUD-like format.

An example of MUD snippet is available in the `examples` folder.

**Note**: this is a preliminary version. This is an on-going research activity.

## How to use it

The first thing to do for using the MUD Aggregator is to copy the `mud_aggregator` folder inside `config/custom_components` folder of your Home Assistant.

The MUD Aggregator is configurable as a [button integration](https://www.home-assistant.io/integrations/button/).
Once configured, you can generate and expose the gateway-level MUD file pressing the related button.

The parameter that you have to confire are the followings:

- name [optional]: to give a custom name to the button;
- interface [optional]: specify the network interface used by your HAss instance (default is `eth0`);
- deploy [optional]: specify if Home Assistant is running in a core/devcontainer (`core`) or on a board or virtual machine (`custom`). Default value is `core`.

Here you can find a confiration example to copy and paste inside `configuration.yaml` file of Home Assistant.

``` YAML
button:
  - platform: mud_aggregator
    name: MUD Aggregator
    interface: eth0
    deploy: core
```

## Citing related papers

This PoC was originally presented to SpliTech 2023. For citing the paper you can import the following BibTex:

``` Bibtex
@inproceedings{CornoMannella2023GWMUD,
  title={A Gateway-based MUD Architecture to Enhance Smart Home Security},
  author={Corno, Fulvio and Mannella, Luca},
  booktitle={Proceedings of the 8th International Conference on Smart and Sustainable Technologies--SpliTech 2023},
  pages={1--6},
  year={2023}, month={June},
  organization={Institute of Electrical and Electronics Engineers (IEEE)},
  keywords = {Cybersecurity, Gateways, Home Assistant, Internet of Things, Manufacturer Usage Description, Smart Home},
  doi = {10.23919/SpliTech58164.2023.10193747}
}
```

You can access the paper at the following links:

- [Paper on ResearchGate](https://www.researchgate.net/publication/370609562_A_Gateway-based_MUD_Architecture_to_Enhance_Smart_Home_Security)
- [Paper on Porto@IRIS](https://hdl.handle.net/11583/2978408)
- [Paper on IEEE Xplore](https://ieeexplore.ieee.org/document/10193747)
